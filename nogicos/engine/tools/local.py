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
        description="""Read the content of a file.

Examples:
- read_file("~/Documents/notes.txt") → Read entire file
- read_file("config.json", limit=50) → Read first 50 lines only
- read_file("C:/Users/WIN/Desktop/report.md") → Read file from absolute path

Parameters:
- path: File path (relative or absolute, supports ~)
- limit: Max lines to read (0 = no limit)

Returns: File content as string, truncated if >50KB""",
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
                    for i, line in enumerate(f):
                        if i >= limit:
                            break
                        lines.append(line)
                    content = ''.join(lines)
                    if i >= limit:
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
        description="""Write content to a file (creates or overwrites).

Examples:
- write_file("output.txt", "Hello World") → Create new file
- write_file("~/notes.md", "# Title\nContent") → Write Markdown file
- write_file("data.json", '{"key": "value"}') → Write JSON file

Parameters:
- path: Target file path
- content: Content to write

Returns: Success message with byte count
Note: Parent directories are created automatically""",
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
        description="""Execute a shell command and return output.

Examples:
- shell_execute("dir") → List directory (Windows)
- shell_execute("ls -la") → List directory (Unix)
- shell_execute("python --version") → Check Python version
- shell_execute("pip list") → List installed packages
- shell_execute("git status") → Check git status

Parameters:
- command: Shell command to run
- timeout: Max seconds to wait (default: 30)

Returns: STDOUT, STDERR, and exit code
BLOCKED: rm -rf /, sudo, format, shutdown commands""",
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
        description="""Search for files matching a glob pattern.

Examples:
- glob_search("*.txt") → All .txt files in current dir
- glob_search("**/*.py") → All Python files (recursive)
- glob_search("**/*.{jpg,png}", "~/Pictures") → Images in Pictures
- glob_search("test_*.py", "src/tests") → Test files in specific folder

Parameters:
- pattern: Glob pattern (*, **, ?, [abc])
- root: Starting directory (default: current)

Returns: List of matching file paths (max 100)""",
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
        description="""Search for text pattern in files (like grep).

Examples:
- grep_search("TODO") → Find TODO in all files
- grep_search("def main", ".", "*.py") → Find main function in Python files
- grep_search("error", "logs/") → Find errors in log directory
- grep_search("import.*pandas", ".", "*.py") → Regex search

Parameters:
- pattern: Text or regex pattern to find
- path: File or directory to search (default: current)
- file_pattern: Filter files by glob (default: *)

Returns: Matching lines with file:line: format (max 50)""",
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
        description="""List files and directories in a path.

Examples:
- list_directory() → List current directory
- list_directory(".") → Same as above
- list_directory("~/Desktop") → List Desktop folder
- list_directory("C:/Users/WIN/Documents") → List Documents

Parameters:
- path: Directory path (default: current directory)

Returns: Formatted list with [DIR] and [FILE] markers and file sizes
Use this FIRST when unsure what files exist in a location""",
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
        description="""Create a new directory (with parents if needed).

Examples:
- create_directory("new_folder") → Create in current dir
- create_directory("~/Desktop/Project/src") → Create nested structure
- create_directory("C:/Users/WIN/Documents/Archive/2024") → Full path

Parameters:
- path: Directory path to create

Returns: Success message
Note: Safe to call even if directory exists""",
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
    
    # ========================================
    # NEW: Essential file operations
    # ========================================
    
    @registry.action(
        description="""Move or rename a file/directory.

Examples:
- move_file("old.txt", "new.txt") → Rename file
- move_file("file.txt", "folder/file.txt") → Move to folder
- move_file("src_folder", "dst_folder") → Move entire folder
- move_file("~/Desktop/doc.pdf", "~/Documents/doc.pdf") → Move between folders

Parameters:
- source: Path to file/folder to move
- destination: Target path

Returns: Success message
Note: Creates destination directory if needed
PROTECTED: Won't move files in .git, code projects, or system folders""",
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
        description="""Delete a file or directory.

Examples:
- delete_file("temp.txt") → Delete single file
- delete_file("empty_folder") → Delete empty directory
- delete_file("old_project", recursive=True) → Delete folder with contents

Parameters:
- path: File or directory to delete
- recursive: If True, delete non-empty directories

Returns: Success message
PROTECTED: Won't delete .git, code projects, or system files""",
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
    
    logger.info(f"Registered {len(registry.get_by_category(ToolCategory.LOCAL))} local tools")
    return registry

