'use client';

import { Button } from '@/components/ui/button';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { LucideX } from 'lucide-react';
import { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

type SettingsDrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Action row pinned below the scroll area, e.g. cancel and save. */
  footer?: ReactNode;
  children: ReactNode;
};

/**
 * Right-hand slide-over used by the chat settings.
 *
 * Built on the Radix dialog primitive rather than `components/ui/sheet.tsx`:
 * that shared sheet hard-codes an 80%-black overlay and a one-third-width panel,
 * while this drawer needs a light backdrop that leaves the conversation
 * readable, a fixed 480px rail, and its own scroll container. It is fixed
 * positioned, so opening it never reflows or covers the chat area's own
 * scrollbar — the drawer scrolls, the conversation underneath does not move.
 */
export function SettingsDrawer({
  open,
  onOpenChange,
  title,
  footer,
  children,
}: SettingsDrawerProps) {
  const { t } = useTranslation();

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className="
            fixed inset-0 z-40 bg-cable-backdrop
            data-[state=open]:animate-in data-[state=open]:fade-in-0
            data-[state=closed]:animate-out data-[state=closed]:fade-out-0
            data-[state=closed]:pointer-events-none
          "
        />
        <DialogPrimitive.Content
          // Radix warns when a dialog has no description; the title alone says
          // everything this panel needs to.
          aria-describedby={undefined}
          className="
            fixed inset-y-0 right-0 z-50 flex w-full max-w-[80vw] flex-col
            border-l border-cable-border bg-cable-surface shadow-cable-drawer outline-none
            transition ease-in-out
            data-[state=open]:animate-in data-[state=open]:slide-in-from-right data-[state=open]:duration-300
            data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=closed]:duration-200
            data-[state=closed]:pointer-events-none
            sm:w-[480px]
          "
          data-testid="chat-detail-settings"
        >
          <header className="flex shrink-0 items-center justify-between gap-4 border-b border-cable-border px-5 py-4">
            <DialogPrimitive.Title className="text-base font-medium text-text-primary">
              {title}
            </DialogPrimitive.Title>

            <DialogPrimitive.Close asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                className="rounded-lg text-text-secondary hover:bg-cable-brand-soft hover:text-cable-brand"
                aria-label={t('common.close', 'Close')}
                data-testid="chat-detail-settings-close"
              >
                <LucideX className="size-4" />
              </Button>
            </DialogPrimitive.Close>
          </header>

          {/* The drawer body is the only scroll container: every setting stays
              reachable on a short viewport without squeezing the fields. */}
          <div
            className="min-h-0 flex-1 overflow-y-auto px-5 py-4"
            data-testid="chat-detail-settings-body"
          >
            {children}
          </div>

          {footer && (
            <footer className="shrink-0 border-t border-cable-border px-5 py-3">
              {footer}
            </footer>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
