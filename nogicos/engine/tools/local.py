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


def _is_path_allowed(path: str) -> bool:
    """Check if path is within allowed directories"""
    abs_path = os.path.abspath(path)
    return any(abs_path.startswith(root) for root in ALLOWED_ROOTS)


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
        description="Read the content of a file. Use limit parameter to read only first N lines for large files.",
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
        description="Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
        category=ToolCategory.LOCAL
    )
    async def write_file(path: str, content: str) -> str:
        """Write content to file"""
        try:
            if not _is_path_allowed(path):
                return f"Error: Access denied to path: {path}"
            
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
        description="Execute a shell command and return the output. Use with caution.",
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
        description="Search for files matching a glob pattern. Example: '**/*.py' finds all Python files.",
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
        description="Search for a pattern in files. Returns matching lines with file paths and line numbers.",
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
        description="List files and directories in a path.",
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
        description="Create a new directory. Creates parent directories if needed.",
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
        description="Move or rename a file or directory from source to destination.",
        category=ToolCategory.LOCAL
    )
    async def move_file(source: str, destination: str) -> str:
        """Move/rename file or directory"""
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
            
            shutil.move(source, destination)
            return f"Successfully moved {source} to {destination}"
            
        except Exception as e:
            logger.error(f"Move file failed: {e}")
            return f"Error moving file: {str(e)}"
    
    @registry.action(
        description="Copy a file or directory from source to destination.",
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
        description="Delete a file or empty directory. Use with caution!",
        category=ToolCategory.LOCAL
    )
    async def delete_file(path: str, recursive: bool = False) -> str:
        """Delete file or directory"""
        import shutil
        try:
            if not _is_path_allowed(path):
                return f"Error: Access denied to path: {path}"
            
            if not os.path.exists(path):
                return f"Error: Path not found: {path}"
            
            # Safety check: don't delete important directories
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

