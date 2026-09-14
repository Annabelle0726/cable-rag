import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  LucideChevronRight,
  LucideLoader,
  LucidePanelLeftOpen,
  LucidePencil,
  LucideSettings,
} from 'lucide-react';
import { ReactNode, useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useRenameSession } from '../hooks/use-rename-session';
import { useSummarizeConversationTitle } from '../hooks/use-summarize-conversation-title';
import { InlineRenameInput } from './inline-rename-input';

type ConversationHeaderProps = {
  chatId?: string;
  sessionId?: string;
  /** Conversation title: the raw first question until it is summarised or renamed. */
  title: string;
  llmId?: string;
  summarizable?: boolean;
  /** Re-opens the conversation list this header only renders without. */
  onExpandSessions?: () => void;
  /** Opens the chat settings drawer, which is reachable here only because the
   * conversation list (and its own settings button) is collapsed. */
  onOpenSettings?: () => void;
  /** Right-hand controls, e.g. the "Multiple models" entry. */
  children?: ReactNode;
};

/**
 * Chat header for one conversation, mounted by the page only while the
 * conversation list is collapsed.
 *
 * Carries no prompt text: the first question used to be printed above the
 * message list and only consumed vertical space. What is left is the collapsed
 * row (title + rename) and, expanded, the right-hand controls.
 */
export function ConversationHeader({
  chatId,
  sessionId,
  title,
  llmId,
  summarizable = false,
  onExpandSessions,
  onOpenSettings,
  children,
}: ConversationHeaderProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);

  const { renameSession, loading: renaming } = useRenameSession();
  const { summarizing } = useSummarizeConversationTitle({
    chatId,
    sessionId,
    currentTitle: title,
    llmId,
    enabled: summarizable,
  });

  const handleToggleExpanded = useCallback(() => {
    setExpanded((previous) => !previous);
  }, []);

  const handleStartEditing = useCallback(() => {
    setEditing(true);
  }, []);

  const handleCancelEditing = useCallback(() => {
    setEditing(false);
  }, []);

  const handleSaveTitle = useCallback(
    async (name: string) => {
      // A conversation that only exists in the browser is created by naming it,
      // so the title the user types is never dropped.
      const renamed = await renameSession({ sessionId, name });
      if (renamed) {
        setEditing(false);
      }
    },
    [renameSession, sessionId],
  );

  const iconButtonClass =
    'size-7 shrink-0 rounded-lg p-0 text-text-secondary transition-colors hover:bg-cable-brand-soft hover:text-cable-brand';

  return (
    <header className="flex min-w-0 items-center justify-between gap-2">
      <div className="group flex min-w-0 items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className={iconButtonClass}
          onClick={handleToggleExpanded}
          aria-expanded={expanded}
          aria-label={expanded ? t('chat.collapseHeader') : t('chat.expandHeader')}
          data-testid="chat-detail-header-toggle"
        >
          <LucideChevronRight
            className={cn('size-4 transition-transform', expanded && 'rotate-90')}
          />
        </Button>

        {editing ? (
          <InlineRenameInput
            value={title}
            onSave={handleSaveTitle}
            onCancel={handleCancelEditing}
            saving={renaming}
            inputClassName="max-w-[min(60vw,32rem)] text-base"
            testId="chat-detail-title-input"
          />
        ) : (
          <>
            <button
              type="button"
              onClick={handleStartEditing}
              title={t('common.rename')}
              data-testid="chat-detail-title"
              className="min-w-0 truncate rounded-lg px-1.5 py-1 text-base font-medium text-text-primary transition-colors hover:bg-cable-brand-soft"
            >
              {title}
            </button>

            <Button
              variant="ghost"
              size="icon"
              className={cn(
                iconButtonClass,
                'opacity-0 group-hover:opacity-100',
              )}
              onClick={handleStartEditing}
              aria-label={t('common.rename')}
              data-testid="chat-detail-title-edit"
            >
              <LucidePencil className="size-3.5" />
            </Button>
          </>
        )}

        {summarizing && (
          <span
            className="flex shrink-0 items-center text-cable-muted"
            title={t('chat.summarizingTitle')}
          >
            <LucideLoader className="size-3.5 animate-spin" />
          </span>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {onOpenSettings && (
          <Button
            variant="ghost"
            size="icon"
            className={iconButtonClass}
            onClick={onOpenSettings}
            aria-label={t('chat.chatSetting')}
            title={t('chat.chatSetting')}
            data-testid="chat-settings-header"
          >
            <LucideSettings className="size-4" />
          </Button>
        )}

        {onExpandSessions && (
          <Button
            variant="ghost"
            size="icon"
            className={iconButtonClass}
            onClick={onExpandSessions}
            aria-label={t('chat.showConversations')}
            title={t('chat.showConversations')}
            data-testid="chat-detail-sessions-open-header"
          >
            <LucidePanelLeftOpen className="size-4" />
          </Button>
        )}

        {expanded && children}
      </div>
    </header>
  );
}
