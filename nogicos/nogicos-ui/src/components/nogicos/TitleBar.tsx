import { Minus, Square, X, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TitleBarProps {
  title?: string;
  onMinimize?: () => void;
  onMaximize?: () => void;
  onClose?: () => void;
  onReconnect?: () => void;
}

export function TitleBar({ 
  title = 'NogicOS', 
  onMinimize, 
  onMaximize, 
  onClose,
  onReconnect,
}: TitleBarProps) {
  // Determine connection status from title
  const isConnected = title === 'NogicOS';
  const isConnecting = title.includes('Connecting');
  const isReconnecting = title.includes('Reconnecting');
  const isDisconnected = title.includes('Disconnected');

  // Call Electron IPC via preload script
  const handleMinimize = () => {
    if (onMinimize) onMinimize();
    else window.nogicos?.windowMinimize?.();
  };

  const handleMaximize = () => {
    if (onMaximize) onMaximize();
    else window.nogicos?.windowMaximize?.();
  };

  const handleClose = () => {
    if (onClose) onClose();
    else window.nogicos?.windowClose?.();
  };

  // Get status indicator
  const getStatusIndicator = () => {
    if (isConnected) {
      return (
        <>
          <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse-soft" />
          <span className="text-xs text-muted-foreground">Ready</span>
        </>
      );
    }
    if (isConnecting || isReconnecting) {
      return (
        <>
          <RefreshCw className="w-3 h-3 text-amber-400 animate-spin" />
          <span className="text-xs text-amber-400">
            {isReconnecting ? 'Reconnecting' : 'Connecting'}
          </span>
        </>
      );
    }
    if (isDisconnected) {
      return (
        <>
          <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
          <span className="text-xs text-red-400">Offline</span>
          {onReconnect && (
            <button
              onClick={onReconnect}
              className="ml-1 px-2 py-0.5 text-[10px] bg-white/10 hover:bg-white/15 rounded text-white/70 hover:text-white transition-colors"
            >
              Retry
            </button>
          )}
        </>
      );
    }
    return null;
  };

  return (
    <header className="electron-titlebar h-11 flex items-center justify-between px-4 bg-background/50 border-b border-border/50 backdrop-blur-sm">
      {/* Logo & Title */}
      <div className="flex items-center gap-2.5">
        <div className={cn(
          "w-5 h-5 rounded-md flex items-center justify-center transition-colors",
          isConnected 
            ? "bg-gradient-to-br from-primary/80 to-primary" 
            : "bg-white/10"
        )}>
          <span className="text-[10px] font-bold text-white">N</span>
        </div>
        <span className={cn(
          "text-sm font-medium",
          isConnected ? "text-muted-foreground" : "text-muted-foreground/60"
        )}>
          NogicOS
        </span>
      </div>

      {/* Status Indicator */}
      <div className="flex items-center gap-2 absolute left-1/2 -translate-x-1/2">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-secondary/50">
          {getStatusIndicator()}
        </div>
      </div>

      {/* Window Controls */}
      <div className="flex items-center gap-0.5">
        <button
          onClick={handleMinimize}
          className="w-8 h-8 flex items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={handleMaximize}
          className="w-8 h-8 flex items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
        >
          <Square className="w-3 h-3" />
        </button>
        <button
          onClick={handleClose}
          className="w-8 h-8 flex items-center justify-center rounded-md text-muted-foreground hover:bg-red-500/90 hover:text-white transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}

// Type declaration for NogicOS preload API
declare global {
  interface Window {
    nogicos?: {
      windowMinimize: () => void;
      windowMaximize: () => void;
      windowClose: () => void;
      windowIsMaximized: () => Promise<boolean>;
      onWindowMaximizeChange: (callback: (isMaximized: boolean) => void) => void;
    };
  }
}
