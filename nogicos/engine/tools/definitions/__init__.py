# Tool Definitions
# Each tool is defined with name, description, parameters (JSON Schema)

from typing import Dict, Any, List

# Tool definition format follows OpenAI function calling schema
TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the local filesystem",
            "parameters": {
                "type": "object",
                "required": ["filepath"],
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "The path of the file to read. Can be absolute or relative to user's home directory"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does",
            "parameters": {
                "type": "object",
                "required": ["filepath", "content"],
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "The path where the file should be written"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and folders in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "dirpath": {
                        "type": "string",
                        "description": "The directory path to list. Defaults to current directory if not specified"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "If true, list files recursively. Default is false"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a terminal command and return its output",
            "parameters": {
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute in the terminal"
                    },
                    "wait_for_completion": {
                        "type": "boolean",
                        "description": "Whether to wait for command completion. Default is true"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_dir",
            "description": "Create a new directory",
            "parameters": {
                "type": "object",
                "required": ["dirpath"],
                "properties": {
                    "dirpath": {
                        "type": "string",
                        "description": "The path of the directory to create"
                    }
                }
            }
        }
    }
]


def get_tool_by_name(name: str) -> Dict[str, Any] | None:
    """Get a tool definition by its name"""
    for tool in TOOL_DEFINITIONS:
        if tool["function"]["name"] == name:
            return tool
    return None


def get_all_tool_names() -> List[str]:
    """Get all available tool names"""
    return [tool["function"]["name"] for tool in TOOL_DEFINITIONS]



