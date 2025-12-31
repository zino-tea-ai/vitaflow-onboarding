# -*- coding: utf-8 -*-
"""
Local Tools - File system and shell tools for NogicOS Agent

Reference: open-interpreter/interpreter/core/computer/files/files.py
           open-interpreter/interpreter/core/computer/terminal/terminal.py
"""

import os
import glob as glob_module
import subprocess
import asyncio
import logging
import re
from typing import Optional, List
from pathlib import Path

from .base import ToolRegistry, ToolCategory, get_registry

logger = logging.getLogger(__name__)

# Security: Define allowed directories for file operations
ALLOWED_ROOTS = [
    os.path.expanduser("~"),  # User home
    os.getcwd(),  # Current working directory
]

# Protected directories that should NOT be modified by file organization tasks
PROTECTED_PATTERNS = [
    "Cursor Project",  # User's main code project
    ".git",            # Git repositories
    "node_modules",    # Node.js dependencies
    "__pycache__",     # Python cache
    ".venv", "venv",   # Python virtual environments
    ".cursor",         # Cursor IDE settings
]

# Code file extensions that indicate a directory is a code project
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss",
    ".java", ".cpp", ".c", ".h", ".hpp", ".go", ".rs", ".rb",
    ".php", ".swift", ".kt", ".scala", ".vue", ".svelte",
}


def _is_path_allowed(path: str) -> bool:
    """Check if path is within allowed directories"""
    abs_path = os.path.abspath(path)
    return any(abs_path.startswith(root) for root in ALLOWED_ROOTS)


def _is_protected_path(path: str) -> tuple[bool, str]:
    """
    Check if path is a protected code directory that should not be modified.
    
    Returns:
        (is_protected, reason)
    """
    abs_path = os.path.abspath(path)
    path_lower = abs_path.lower()
    
    # Check for protected patterns in path
    for pattern in PROTECTED_PATTERNS:
        if pattern.lower() in path_lower:
            return True, f"Path contains protected pattern: {pattern}"
    
    # Check if directory contains .git (it's a code repository)
    dir_to_check = abs_path if os.path.isdir(abs_path) else os.path.dirname(abs_path)
    if os.path.exists(os.path.join(dir_to_check, ".git")):
        return True, "This is a git repository (code project)"
    
    # Check parent directories for .git
    current = dir_to_check
    for _ in range(5):  # Check up to 5 levels up
        parent = os.path.dirname(current)
        if parent == current:  # Reached root
            break
        if os.path.exists(os.path.join(parent, ".git")):
            return True, "This path is inside a git repository (code project)"
        current = parent
    
    return False, ""


def _check_file_safety(path: str, operation: str) -> tuple[bool, str]:
    """
    Check if a file operation is safe to perform.
    
    Args:
        path: Path to check
        operation: Operation type (move, delete, write)
        
    Returns:
        (is_safe, error_message)
    """
    # Check basic permission
    if not _is_path_allowed(path):
        return False, f"Access denied to path: {path}"
    
    # Check for protected directories
    is_protected, reason = _is_protected_path(path)
    if is_protected:
        return False, f"PROTECTED: {reason}. This path should not be modified by file organization tasks."
    
    # Check file extension for code files
    if os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        if ext in CODE_EXTENSIONS:
            return False, f"PROTECTED: This is a code file ({ext}). Code files should not be modified by file organization tasks."
    
    return True, ""


def register_local_tools(registry: Optional[ToolRegistry] = None) -> ToolRegistry:
    """
    Register all local system tools to the registry.
    
    Args:
        registry: Optional registry to use. If None, uses global registry.
        
    Returns:
        The registry with local tools registered.
    """
    if registry is None:
        registry = get_registry()
    
    @registry.action(
        description="""Read file content from local filesystem.

WHEN TO USE:
- Reading known file paths
- Viewing configuration, source code, or data files
- Checking file content before modification

WHEN NOT TO USE:
- Finding files by pattern → use glob_search
- Searching content across files → use grep_search
- Listing directory contents → use list_directory

Parameters:
- path: File path (relative/absolute, supports ~)
- limit: Max lines (0 = unlimited, default: 0)

Returns: File content (truncated if >50KB)""",
        category=ToolCategory.LOCAL
    )
    async def read_file(path: str, limit: int = 0) -> str:
        """Read file content"""
        try:
            if not _is_path_allowed(path):
                return f"Error: Access denied to path: {path}"
            
            if not os.path.exists(path):
                return f"Error: File not found: {path}"
            
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                if limit > 0:
                    lines = []
                    line_count = 0
                    for line_count, line in enumerate(f):
                        if line_count >= limit:
                            break
                        lines.append(line)
                    content = ''.join(lines)
                    if line_count >= limit:
                        content += f"\n... (showing first {limit} lines)"
                else:
                    content = f.read()
            
            # Limit output size
            max_size = 50000
            if len(content) > max_size:
                content = content[:max_size] + f"\n... (truncated, total {len(content)} chars)"
            
            return content
            
        except Exception as e:
            logger.error(f"Read file failed: {e}")
            return f"Error reading file: {str(e)}"
    
    @registry.action(
        description="""Write content to file (creates or overwrites).

WHEN TO USE:
- Creating new files
- Overwriting entire file content
- Saving generated code, config, or data

WHEN NOT TO USE:
- Partial text replacement → use search_replace
- Appending to file → use append_file
- Editing existing code → prefer search_replace

Parameters:
- path: Target file path
- content: Content to write

Note: Creates parent directories automatically. Overwrites existing files.""",
        category=ToolCategory.LOCAL
    )
    async def write_file(path: str, content: str) -> str:
        """Write content to file"""
        try:
            # Safety check for code files
            is_safe, error = _check_file_safety(path, "write")
            if not is_safe:
                return f"Error: {error}"
            
            # Create parent directories if needed
            parent = os.path.dirname(path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return f"Successfully wrote {len(content)} characters to {path}"
            
        except Exception as e:
            logger.error(f"Write file failed: {e}")
            return f"Error writing file: {str(e)}"
    
    @registry.action(
        description="Append content to the end of a file. Creates the file if it doesn't exist.",
        category=ToolCategory.LOCAL
    )
    async def append_file(path: str, content: str) -> str:
        """Append content to file"""
        try:
            if not _is_path_allowed(path):
                return f"Error: Access denied to path: {path}"
            
            with open(path, 'a', encoding='utf-8') as f:
                f.write(content)
            
            return f"Successfully appended {len(content)} characters to {path}"
            
        except Exception as e:
            logger.error(f"Append file failed: {e}")
            return f"Error appending to file: {str(e)}"
    
    @registry.action(
        description="""Execute shell command and return output.

WHEN TO USE:
- Installing packages (npm, pip, etc.)
- Running scripts or build commands
- Git operations
- System commands without dedicated tools

WHEN NOT TO USE:
- Listing directories → use list_directory
- Reading files → use read_file
- Searching files → use glob_search or grep_search

Parameters:
- command: Shell command to execute
- timeout: Max seconds (default: 30)

Returns: STDOUT, STDERR, exit code
Security: Blocks rm -rf /, sudo, format, shutdown""",
        category=ToolCategory.LOCAL
    )
    async def shell_execute(command: str, timeout: int = 30) -> str:
        """Execute shell command"""
        try:
            # Security: Block dangerous commands
            dangerous_patterns = [
                r'\brm\s+-rf\s+/',
                r'\bsudo\b',
                r'\bformat\b',
                r'\bdel\s+/[sf]',
                r'\bshutdown\b',
                r'\breboot\b',
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, command, re.IGNORECASE):
                    return f"Error: Command blocked for security reasons"
            
            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd()
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Command timed out after {timeout} seconds"
            
            output = stdout.decode('utf-8', errors='replace')
            error = stderr.decode('utf-8', errors='replace')
            
            result = []
            if output:
                result.append(f"STDOUT:\n{output}")
            if error:
                result.append(f"STDERR:\n{error}")
            result.append(f"Exit code: {process.returncode}")
            
            return '\n'.join(result)
            
        except Exception as e:
            logger.error(f"Shell execute failed: {e}")
            return f"Error executing command: {str(e)}"
    
    @registry.action(
        description="""Find files by name pattern (glob).

WHEN TO USE:
- Finding files by extension (*.py, *.tsx)
- Locating files by name pattern (test_*, config.*)
- Listing specific file types in a directory

WHEN NOT TO USE:
- Searching file content → use grep_search
- Semantic code search → use codebase_search
- Listing all directory contents → use list_directory

Parameters:
- pattern: Glob pattern (*, **, ?, [abc])
- root: Starting directory (default: current)

Returns: Matching file paths (max 100)""",
        category=ToolCategory.LOCAL
    )
    async def glob_search(pattern: str, root: str = ".") -> str:
        """Find files matching pattern"""
        try:
            if not _is_path_allowed(root):
                return f"Error: Access denied to path: {root}"
            
            # Use glob to find files
            search_path = os.path.join(root, pattern)
            matches = glob_module.glob(search_path, recursive=True)
            
            # Limit results
            max_results = 100
            if len(matches) > max_results:
                matches = matches[:max_results]
                truncated = True
            else:
                truncated = False
            
            if not matches:
                return f"No files found matching pattern: {pattern}"
            
            result = f"Found {len(matches)} files:\n"
            result += '\n'.join(matches)
            
            if truncated:
                result += f"\n... (showing first {max_results} results)"
            
            return result
            
        except Exception as e:
            logger.error(f"Glob search failed: {e}")
            return f"Error searching files: {str(e)}"
    
    @registry.action(
        description="""Search text/regex pattern in files (like grep/ripgrep).

WHEN TO USE:
- Finding exact text or regex matches in code
- Locating function/variable definitions
- Searching logs or data files for patterns

WHEN NOT TO USE:
- Finding files by name → use glob_search
- Semantic/meaning-based search → use codebase_search
- Reading known file → use read_file

Parameters:
- pattern: Text or regex pattern
- path: Search path (default: current directory)
- file_pattern: Filter by glob (default: *)

Returns: Matching lines as file:line:content (max 50)""",
        category=ToolCategory.LOCAL
    )
    async def grep_search(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
        """Search for pattern in files"""
        try:
            if not _is_path_allowed(path):
                return f"Error: Access denied to path: {path}"
            
            results = []
            max_results = 50
            
            # Find files to search
            if os.path.isfile(path):
                files = [path]
            else:
                search_path = os.path.join(path, "**", file_pattern)
                files = glob_module.glob(search_path, recursive=True)
            
            regex = re.compile(pattern, re.IGNORECASE)
            
            for filepath in files:
                if not os.path.isfile(filepath):
                    continue
                    
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(f"{filepath}:{line_num}: {line.strip()}")
                                if len(results) >= max_results:
                                    break
                except:
                    continue
                
                if len(results) >= max_results:
                    break
            
            if not results:
                return f"No matches found for pattern: {pattern}"
            
            result = f"Found {len(results)} matches:\n"
            result += '\n'.join(results)
            
            if len(results) >= max_results:
                result += f"\n... (showing first {max_results} results)"
            
            return result
            
        except Exception as e:
            logger.error(f"Grep search failed: {e}")
            return f"Error searching: {str(e)}"
    
    @registry.action(
        description="""List directory contents.

WHEN TO USE:
- Exploring unfamiliar directories
- Checking what files exist before operations
- Getting overview of folder structure

WHEN NOT TO USE:
- Finding specific file types → use glob_search
- Reading file content → use read_file
- Searching inside files → use grep_search

Parameters:
- path: Directory path (default: current)

Returns: List with [DIR]/[FILE] markers and sizes
TIP: Use this first when unsure what files exist""",
        category=ToolCategory.LOCAL
    )
    async def list_directory(path: str = ".") -> str:
        """List directory contents"""
        try:
            if not _is_path_allowed(path):
                return f"Error: Access denied to path: {path}"
            
            if not os.path.exists(path):
                return f"Error: Path not found: {path}"
            
            if not os.path.isdir(path):
                return f"Error: Not a directory: {path}"
            
            entries = []
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                    entries.append(f"[DIR]  {entry}/")
                else:
                    size = os.path.getsize(full_path)
                    entries.append(f"[FILE] {entry} ({size} bytes)")
            
            if not entries:
                return f"Directory is empty: {path}"
            
            return f"Contents of {path}:\n" + '\n'.join(sorted(entries))
            
        except Exception as e:
            logger.error(f"List directory failed: {e}")
            return f"Error listing directory: {str(e)}"
    
    @registry.action(
        description="""Create directory (with parent directories).

WHEN TO USE:
- Creating new folder structure
- Setting up project directories
- Preparing output locations

Note: Safe if directory already exists (no error).

Parameters:
- path: Directory path to create

Returns: Success message""",
        category=ToolCategory.LOCAL
    )
    async def create_directory(path: str) -> str:
        """Create directory"""
        try:
            if not _is_path_allowed(path):
                return f"Error: Access denied to path: {path}"
            
            os.makedirs(path, exist_ok=True)
            return f"Successfully created directory: {path}"
            
        except Exception as e:
            logger.error(f"Create directory failed: {e}")
            return f"Error creating directory: {str(e)}"
    
    @registry.action(
        description="Get the current working directory.",
        category=ToolCategory.LOCAL
    )
    async def get_cwd() -> str:
        """Get current working directory"""
        return os.getcwd()
    
    @registry.action(
        description="""Perform exact string replacement in files.

WHEN TO USE:
- Renaming variables/functions across files
- Fixing specific text patterns
- Precise code modifications
- Updating imports or references

WHEN NOT TO USE:
- Creating new files → use write_file
- Overwriting entire file → use write_file
- Complex regex transforms → use shell_execute with sed

Parameters:
- file_path: Target file
- old_string: Text to find (must be unique)
- new_string: Replacement text
- replace_all: Replace all occurrences (default: False)

Note: old_string must match exactly including whitespace.""",
        category=ToolCategory.LOCAL
    )
    async def search_replace(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        """Perform exact string replacement in file"""
        try:
            if not _is_path_allowed(file_path):
                return f"Error: Access denied to path: {file_path}"
            
            if not os.path.exists(file_path):
                return f"Error: File not found: {file_path}"
            
            if not os.path.isfile(file_path):
                return f"Error: Not a file: {file_path}"
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check if old_string exists
            count = content.count(old_string)
            if count == 0:
                return f"Error: '{old_string[:50]}...' not found in {file_path}"
            
            # If not replace_all and multiple matches, warn
            if not replace_all and count > 1:
                return f"Error: Found {count} occurrences of '{old_string[:50]}...'. Use replace_all=True or provide more unique string."
            
            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replaced_count = count
            else:
                new_content = content.replace(old_string, new_string, 1)
                replaced_count = 1
            
            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return f"Successfully replaced {replaced_count} occurrence(s) in {file_path}"
            
        except Exception as e:
            logger.error(f"Search replace failed: {e}")
            return f"Error performing replacement: {str(e)}"
    
    # ========================================
    # NEW: Essential file operations
    # ========================================
    
    @registry.action(
        description="""Move or rename file/directory.

WHEN TO USE:
- Renaming files or folders
- Moving files between directories
- Reorganizing project structure

WHEN NOT TO USE:
- Copying files → use copy_file
- Deleting files → use delete_file

Parameters:
- source: Path to move from
- destination: Target path

Note: Creates destination directory if needed.
PROTECTED: Won't move .git, code projects, system folders.""",
        category=ToolCategory.LOCAL
    )
    async def move_file(source: str, destination: str) -> str:
        """Move/rename file or directory"""
        import shutil
        try:
            # Safety check for source
            is_safe, error = _check_file_safety(source, "move")
            if not is_safe:
                return f"Error: {error}"
            
            # Safety check for destination
            is_safe, error = _check_file_safety(destination, "move")
            if not is_safe:
                return f"Error: {error}"
            
            if not os.path.exists(source):
                return f"Error: Source not found: {source}"
            
            # Create destination directory if needed
            dest_dir = os.path.dirname(destination)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            
            shutil.move(source, destination)
            return f"Successfully moved {source} to {destination}"
            
        except Exception as e:
            logger.error(f"Move file failed: {e}")
            return f"Error moving file: {str(e)}"
    
    @registry.action(
        description="""Copy a file or directory.

Examples:
- copy_file("doc.txt", "doc_backup.txt") → Copy file
- copy_file("folder", "folder_copy") → Copy entire folder
- copy_file("~/config.json", "~/backup/config.json") → Copy to different location

Parameters:
- source: Path to copy from
- destination: Path to copy to

Returns: Success message
Note: Preserves file metadata, creates destination dir if needed""",
        category=ToolCategory.LOCAL
    )
    async def copy_file(source: str, destination: str) -> str:
        """Copy file or directory"""
        import shutil
        try:
            if not _is_path_allowed(source):
                return f"Error: Access denied to source path: {source}"
            if not _is_path_allowed(destination):
                return f"Error: Access denied to destination path: {destination}"
            
            if not os.path.exists(source):
                return f"Error: Source not found: {source}"
            
            # Create destination directory if needed
            dest_dir = os.path.dirname(destination)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            
            if os.path.isdir(source):
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)
            
            return f"Successfully copied {source} to {destination}"
            
        except Exception as e:
            logger.error(f"Copy file failed: {e}")
            return f"Error copying file: {str(e)}"
    
    @registry.action(
        description="""Delete file or directory.

WHEN TO USE:
- Removing temporary files
- Cleaning up old directories
- Deleting generated outputs

WHEN NOT TO USE:
- Moving files → use move_file
- Archiving → use move_file to backup location

Parameters:
- path: File or directory to delete
- recursive: Delete non-empty directories (default: False)

PROTECTED: Won't delete .git, code projects, system files.""",
        category=ToolCategory.LOCAL
    )
    async def delete_file(path: str, recursive: bool = False) -> str:
        """Delete file or directory"""
        import shutil
        try:
            # Enhanced safety check
            is_safe, error = _check_file_safety(path, "delete")
            if not is_safe:
                return f"Error: {error}"
            
            if not os.path.exists(path):
                return f"Error: Path not found: {path}"
            
            # Additional safety check: don't delete important directories
            danger_paths = [
                os.path.expanduser("~"),
                "C:\\",
                "C:\\Windows",
                "C:\\Program Files",
                "/",
                "/home",
                "/usr",
            ]
            abs_path = os.path.abspath(path)
            if abs_path in danger_paths:
                return f"Error: Refusing to delete protected path: {path}"
            
            if os.path.isdir(path):
                if recursive:
                    shutil.rmtree(path)
                else:
                    os.rmdir(path)  # Only removes empty dirs
            else:
                os.remove(path)
            
            return f"Successfully deleted: {path}"
            
        except Exception as e:
            logger.error(f"Delete file failed: {e}")
            return f"Error deleting: {str(e)}"
    
    @registry.action(
        description="Check if a file or directory exists at the given path.",
        category=ToolCategory.LOCAL
    )
    async def path_exists(path: str) -> str:
        """Check if path exists"""
        try:
            if not _is_path_allowed(path):
                return f"Error: Access denied to path: {path}"
            
            exists = os.path.exists(path)
            is_file = os.path.isfile(path)
            is_dir = os.path.isdir(path)
            
            if exists:
                type_str = "file" if is_file else "directory" if is_dir else "unknown"
                size = os.path.getsize(path) if is_file else None
                return f"Exists: True, Type: {type_str}" + (f", Size: {size} bytes" if size else "")
            else:
                return f"Exists: False"
            
        except Exception as e:
            return f"Error checking path: {str(e)}"
    
    @registry.action(
        description="""Read linter errors for files.

WHEN TO USE:
- After editing code files
- Checking for syntax errors
- Validating code quality
- Before committing changes

WHEN NOT TO USE:
- Reading file content → use read_file
- Running tests → use shell_execute

Parameters:
- paths: File paths to lint (Python: pylint, JS: eslint)
- linter: Override linter (auto-detected by extension)

Returns: List of errors with line numbers and messages""",
        category=ToolCategory.LOCAL
    )
    async def read_lints(paths: List[str], linter: str = None) -> str:
        """Read linter errors for specified files"""
        try:
            results = []
            
            for path in paths:
                if not _is_path_allowed(path):
                    results.append(f"Error: Access denied to {path}")
                    continue
                
                if not os.path.exists(path):
                    results.append(f"Error: File not found: {path}")
                    continue
                
                ext = os.path.splitext(path)[1].lower()
                
                # Auto-detect linter
                if linter:
                    lint_cmd = linter
                elif ext == '.py':
                    lint_cmd = 'pylint'
                elif ext in ['.js', '.ts', '.jsx', '.tsx']:
                    lint_cmd = 'eslint'
                else:
                    results.append(f"No linter configured for {ext} files")
                    continue
                
                # Run linter
                try:
                    if lint_cmd == 'pylint':
                        cmd = f'python -m pylint --output-format=text --score=no "{path}"'
                    elif lint_cmd == 'eslint':
                        cmd = f'npx eslint --format=stylish "{path}"'
                    else:
                        cmd = f'{lint_cmd} "{path}"'
                    
                    process = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=os.getcwd()
                    )
                    
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=30
                    )
                    
                    output = stdout.decode('utf-8', errors='replace')
                    error = stderr.decode('utf-8', errors='replace')
                    
                    if output.strip():
                        results.append(f"=== {path} ===\n{output.strip()}")
                    elif process.returncode == 0:
                        results.append(f"=== {path} ===\nNo linter errors found.")
                    else:
                        results.append(f"=== {path} ===\n{error.strip() if error else 'Linter returned errors'}")
                        
                except asyncio.TimeoutError:
                    results.append(f"=== {path} ===\nLinter timed out")
                except Exception as e:
                    results.append(f"=== {path} ===\nLinter error: {str(e)}")
            
            if not results:
                return "No files to lint"
            
            return '\n\n'.join(results)
            
        except Exception as e:
            logger.error(f"Read lints failed: {e}")
            return f"Error reading lints: {str(e)}"
    
    logger.info(f"Registered {len(registry.get_by_category(ToolCategory.LOCAL))} local tools")
    return registry

