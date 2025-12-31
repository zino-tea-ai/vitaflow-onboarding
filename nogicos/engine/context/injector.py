# -*- coding: utf-8 -*-
"""
Context Injector - Automatic context collection and injection

This is the main component that collects and injects context into messages,
similar to how Cursor enriches each message with <user_info>, <project_layout>,
<open_and_recently_viewed_files>, etc.
"""

import os
import platform
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

import sqlite3
from pathlib import Path

from .workspace import get_workspace_layout, get_important_files
from .terminal import get_terminal_tracker

# Database path (same as cursor_tools.py)
_MEMORY_DB_PATH = Path(__file__).parent.parent.parent / "data" / "agent_state.db"


def _get_memories_from_db(namespace: str = "default", limit: int = 5) -> List[Dict[str, str]]:
    """Get memories from database for prompt injection.
    
    Always includes 'default' namespace memories to ensure user preferences
    are available across all sessions.
    """
    try:
        if not _MEMORY_DB_PATH.exists():
            return []
        
        with sqlite3.connect(str(_MEMORY_DB_PATH)) as conn:
            cursor = conn.cursor()
            # Always include default namespace to get user preferences
            # This ensures memories like "prefers pnpm" are always available
            cursor.execute("""
                SELECT id, title, content 
                FROM memories 
                WHERE namespace IN (?, 'default')
                ORDER BY updated_at DESC
                LIMIT ?
            """, (namespace, limit))
            
            rows = cursor.fetchall()
            memories = [{"id": r[0], "title": r[1], "content": r[2]} for r in rows]
            
            # Debug logging (can be removed later)
            if memories:
                import logging
                logging.getLogger("nogicos.context").debug(
                    f"[Context] Injecting {len(memories)} memories"
                )
            
            return memories
    except Exception as e:
        import logging
        logging.getLogger("nogicos.context").warning(f"[Context] Memory load failed: {e}")
        return []


@dataclass
class ContextConfig:
    """Configuration for context injection"""
    # What to include
    include_user_info: bool = True
    include_workspace_layout: bool = True
    include_terminal_info: bool = True
    include_recent_files: bool = True
    include_memories: bool = True
    
    # Workspace settings
    workspace_path: Optional[str] = None
    workspace_max_depth: int = 2
    
    # Recent files (IDE integration would provide these)
    recent_files: List[str] = field(default_factory=list)
    open_files: List[str] = field(default_factory=list)
    focused_file: Optional[str] = None
    
    # Memory/rules
    workspace_rules: Optional[str] = None
    user_memories: List[Dict[str, str]] = field(default_factory=list)


class ContextInjector:
    """
    Collects and injects context into user messages.
    
    This class implements Cursor-style context injection:
    - <user_info>: OS, date, shell, workspace path
    - <project_layout>: Workspace directory structure
    - <open_and_recently_viewed_files>: Files user is working with
    - <terminal_files_information>: Recent terminal commands
    - <memories>: User memories and preferences
    - <workspace_rules>: Project-specific rules
    """
    
    def __init__(self, default_workspace: Optional[str] = None):
        """
        Initialize context injector.
        
        Args:
            default_workspace: Default workspace path if not provided in config
        """
        self.default_workspace = default_workspace or os.getcwd()
        self.terminal_tracker = get_terminal_tracker()
    
    def inject(
        self,
        message: str,
        session_id: str = "default",
        config: Optional[ContextConfig] = None,
    ) -> str:
        """
        Inject context into a user message.
        
        Args:
            message: Original user message
            session_id: Session ID for terminal history
            config: Context configuration (uses defaults if not provided)
            
        Returns:
            Message with context prepended
        """
        if config is None:
            config = ContextConfig(workspace_path=self.default_workspace)
        
        sections = []
        
        # 1. User Info (always include)
        if config.include_user_info:
            sections.append(self._user_info(config))
        
        # 2. Workspace Layout (first message in session typically)
        if config.include_workspace_layout and config.workspace_path:
            sections.append(self._workspace_layout(config))
        
        # 3. Open and Recent Files
        if config.include_recent_files and (config.recent_files or config.open_files):
            sections.append(self._recent_files(config))
        
        # 4. Terminal Info
        if config.include_terminal_info:
            terminal_info = self.terminal_tracker.format_for_prompt(session_id)
            if terminal_info:
                sections.append(terminal_info)
        
        # 5. Workspace Rules (project-specific)
        if config.workspace_rules:
            sections.append(f"<workspace_rules>\n{config.workspace_rules}\n</workspace_rules>")
        
        # 6. User Memories (from config or auto-loaded from DB)
        if config.include_memories:
            # Auto-load from database if not provided
            if not config.user_memories:
                config.user_memories = _get_memories_from_db(
                    namespace=session_id,
                    limit=5
                )
            
            if config.user_memories:
                sections.append(self._memories(config))
        
        # Combine context with message
        if sections:
            context = "\n\n".join(sections)
            return f"{context}\n\n<user_query>\n{message}\n</user_query>"
        else:
            return message
    
    def _user_info(self, config: ContextConfig) -> str:
        """Generate <user_info> section"""
        workspace = config.workspace_path or self.default_workspace
        
        # Detect shell
        shell = os.environ.get("SHELL", os.environ.get("COMSPEC", "unknown"))
        
        return f"""<user_info>
OS Version: {platform.system()} {platform.release()}
Current Date: {datetime.now().strftime("%A %b %d, %Y")}
Shell: {shell}
Workspace Path: {workspace}
</user_info>"""
    
    def _workspace_layout(self, config: ContextConfig) -> str:
        """Generate <project_layout> section"""
        workspace = config.workspace_path or self.default_workspace
        
        layout = get_workspace_layout(
            workspace,
            max_depth=config.workspace_max_depth,
        )
        
        # Get important files
        important = get_important_files(workspace)
        important_str = ""
        if important:
            important_str = f"\n\nKey files: {', '.join(important)}"
        
        return f"""<project_layout>
{layout}{important_str}

Note: This is a snapshot. Run list_directory for current state.
</project_layout>"""
    
    def _recent_files(self, config: ContextConfig) -> str:
        """Generate <open_and_recently_viewed_files> section"""
        lines = ["<open_and_recently_viewed_files>"]
        
        if config.open_files:
            lines.append("Open files:")
            for f in config.open_files[:5]:
                marker = " (focused)" if f == config.focused_file else ""
                lines.append(f"  - {f}{marker}")
        
        if config.recent_files:
            lines.append("\nRecently viewed:")
            for f in config.recent_files[:5]:
                lines.append(f"  - {f}")
        
        lines.append("</open_and_recently_viewed_files>")
        
        return "\n".join(lines)
    
    def _memories(self, config: ContextConfig) -> str:
        """Generate <memories> section"""
        lines = ["<memories>"]
        
        for mem in config.user_memories[:5]:  # Limit to 5 most relevant
            title = mem.get("title", "Untitled")
            content = mem.get("content", "")
            lines.append(f"- [{title}]: {content}")
        
        lines.append("</memories>")
        
        return "\n".join(lines)
    
    def create_first_message_context(
        self,
        workspace_path: str,
        session_id: str = "default",
    ) -> ContextConfig:
        """
        Create a full context config for the first message in a session.
        
        First message typically includes full workspace layout.
        Subsequent messages can use lighter context.
        
        Args:
            workspace_path: Workspace root path
            session_id: Session ID
            
        Returns:
            ContextConfig with full context enabled
        """
        return ContextConfig(
            include_user_info=True,
            include_workspace_layout=True,
            include_terminal_info=True,
            include_recent_files=False,  # No files yet
            include_memories=True,
            workspace_path=workspace_path,
            workspace_max_depth=2,
        )
    
    def create_subsequent_message_context(
        self,
        workspace_path: str,
        session_id: str = "default",
        recent_files: Optional[List[str]] = None,
    ) -> ContextConfig:
        """
        Create a lighter context config for subsequent messages.
        
        Omits workspace layout (already sent), focuses on recent changes.
        
        Args:
            workspace_path: Workspace root path
            session_id: Session ID
            recent_files: Recently accessed files
            
        Returns:
            ContextConfig with lighter context
        """
        return ContextConfig(
            include_user_info=True,
            include_workspace_layout=False,  # Already sent
            include_terminal_info=True,
            include_recent_files=bool(recent_files),
            include_memories=False,  # Already sent
            workspace_path=workspace_path,
            recent_files=recent_files or [],
        )


# Global instance for convenience
_injector: Optional[ContextInjector] = None


def get_context_injector(workspace: Optional[str] = None) -> ContextInjector:
    """Get or create global context injector instance"""
    global _injector
    if _injector is None:
        _injector = ContextInjector(default_workspace=workspace)
    return _injector

