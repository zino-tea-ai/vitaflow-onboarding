import { useState } from 'react';
import { Check, Copy, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import './styles/cursor-theme.css';

interface DiffLine {
  type: 'add' | 'del' | 'context';
  content: string;
  lineNumber?: number;
}

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
  diff?: {
    additions: number;
    deletions: number;
    lines?: DiffLine[];
  };
  className?: string;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
}

/**
 * CodeBlock - Cursor-style code display with diff support
 * 
 * Features:
 * - Filename and diff stats header
 * - Syntax highlighting (via CSS classes)
 * - Diff view with green/red lines
 * - Copy button
 * - Collapsible
 */
export function CodeBlock({
  code,
  language,
  filename,
  diff,
  className,
  collapsible = false,
  defaultCollapsed = false,
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const hasDiff = diff && (diff.additions > 0 || diff.deletions > 0);

  return (
    <div className={cn('chat-code-block group relative', className)}>
      {/* Header */}
      {(filename || hasDiff || collapsible) && (
        <div className="chat-code-header flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {collapsible && (
              <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className="text-[var(--chat-text-secondary)] hover:text-[var(--chat-text-primary)]"
              >
                {isCollapsed ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronUp className="w-4 h-4" />
                )}
              </button>
            )}
            {filename && (
              <span className="chat-code-filename font-medium">{filename}</span>
            )}
            {hasDiff && (
              <span className="flex items-center gap-1 text-xs">
                {diff.additions > 0 && (
                  <span className="chat-code-stats-add">+{diff.additions}</span>
                )}
                {diff.deletions > 0 && (
                  <span className="chat-code-stats-del">-{diff.deletions}</span>
                )}
              </span>
            )}
            {language && !filename && (
              <span className="text-[10px] text-[var(--chat-text-secondary)] uppercase tracking-wider">
                {language}
              </span>
            )}
          </div>
          
          {/* Copy Button */}
          <button
            onClick={handleCopy}
            className="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--chat-text-secondary)] hover:text-[var(--chat-text-primary)] p-1"
            title="Copy code"
          >
            {copied ? (
              <Check className="w-4 h-4 text-[var(--chat-accent-green)]" />
            ) : (
              <Copy className="w-4 h-4" />
            )}
          </button>
        </div>
      )}

      {/* Code Content */}
      {!isCollapsed && (
        <div className="overflow-x-auto">
          {diff?.lines ? (
            // Diff view
            <pre className="text-[13px] font-mono leading-relaxed">
              {diff.lines.map((line, i) => (
                <div
                  key={i}
                  className={cn(
                    'px-2 -mx-4',
                    line.type === 'add' && 'chat-diff-add',
                    line.type === 'del' && 'chat-diff-del'
                  )}
                >
                  <span className="text-[var(--chat-text-muted)] w-8 inline-block select-none">
                    {line.type === 'add' ? '+' : line.type === 'del' ? '-' : ' '}
                  </span>
                  <span className={cn(
                    line.type === 'add' && 'text-[var(--chat-accent-green)]',
                    line.type === 'del' && 'text-[var(--chat-accent-red)]',
                    line.type === 'context' && 'text-[var(--chat-text-primary)]'
                  )}>
                    {line.content}
                  </span>
                </div>
              ))}
            </pre>
          ) : (
            // Regular code view
            <pre className="text-[13px] font-mono text-[var(--syntax-function)] leading-relaxed">
              <code>{code}</code>
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

