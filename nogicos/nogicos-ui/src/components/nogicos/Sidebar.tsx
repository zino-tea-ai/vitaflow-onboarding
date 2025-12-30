import { useState } from 'react';
import { 
  MessageSquare, 
  Plus, 
  Search, 
  Settings, 
  Trash2,
  MoreHorizontal,
  Clock
} from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

export interface Session {
  id: string;
  title: string;
  preview: string;
  timestamp: Date;
  isActive?: boolean;
}

interface SidebarProps {
  sessions: Session[];
  activeSessionId?: string;
  onNewSession: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onOpenSettings?: () => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  onNewSession,
  onSelectSession,
  onDeleteSession,
  onOpenSettings,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredSessions = sessions.filter(
    (session) =>
      session.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      session.preview.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <aside className="w-64 flex flex-col bg-card/30 border-r border-border/50">
      {/* Header */}
      <div className="p-3 space-y-3">
        {/* New Chat Button */}
        <Button 
          onClick={onNewSession}
          className="w-full justify-start gap-2 glass-button h-10"
          variant="ghost"
        >
          <Plus className="w-4 h-4" />
          <span>New Session</span>
          <kbd className="ml-auto text-[10px] text-muted-foreground bg-secondary px-1.5 py-0.5 rounded">
            ⌘K
          </kbd>
        </Button>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search sessions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="glass-input pl-9 h-9"
          />
        </div>
      </div>

      {/* Session List */}
      <ScrollArea className="flex-1 px-2">
        <div className="space-y-1 pb-2">
          {filteredSessions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">
              {searchQuery ? 'No sessions found' : 'No sessions yet'}
            </div>
          ) : (
            filteredSessions.map((session, index) => (
              <div
                key={session.id}
                className={cn(
                  'group relative animate-slide-up',
                  `delay-${Math.min(index + 1, 5)}`
                )}
                style={{ opacity: 0 }}
              >
                <button
                  onClick={() => onSelectSession(session.id)}
                  className={cn(
                    'w-full text-left px-3 py-2.5 rounded-xl transition-all',
                    'hover:bg-secondary/80',
                    activeSessionId === session.id
                      ? 'bg-primary/10 border-l-2 border-primary'
                      : 'border-l-2 border-transparent'
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <MessageSquare className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium text-foreground truncate">
                          {session.title}
                        </span>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button
                              className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-secondary/80 transition-opacity"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <MoreHorizontal className="w-3.5 h-3.5 text-muted-foreground" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-36">
                            <DropdownMenuItem
                              onClick={() => onDeleteSession(session.id)}
                              className="text-destructive focus:text-destructive"
                            >
                              <Trash2 className="w-4 h-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                      <p className="text-xs text-muted-foreground truncate mt-0.5">
                        {session.preview}
                      </p>
                      <div className="flex items-center gap-1 mt-1.5 text-[10px] text-muted-foreground/70">
                        <Clock className="w-3 h-3" />
                        {formatTime(session.timestamp)}
                      </div>
                    </div>
                  </div>
                </button>
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="p-3 border-t border-border/50">
        <button
          onClick={onOpenSettings}
          className="sidebar-item w-full"
        >
          <Settings className="w-4 h-4" />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}

