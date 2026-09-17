import { RAGFlowAvatar } from '@/components/ragflow-avatar';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { formatDate } from '@/utils/date';
import { t } from 'i18next';
import { ChevronRight } from 'lucide-react';

/**
 * Card shell shared by the home page application tiles (chat / search / agent /
 * memory). Sizing is fluid so the tiles can live in the responsive grid.
 */
const applicationCardClass = cn(
  // `card-interactive` supplies the pointer cursor and the colour-only hover
  // tint — no translate: the overflow-auto grid these tiles live in would clip
  // a lifted card, so the lift is the ceramic shadow instead.
  'card-interactive group h-full w-full rounded-xl px-4 py-3',
  // Translucent glass tint, matching the knowledge-base cards, so the page's
  // glow reads through the tile instead of stopping at an opaque surface. The
  // ceramic shell adds the inner rim light and the drop shadow per theme.
  'border border-ceramic-border bg-glass shadow-ceramic',
  'hover:border-ceramic-border-hover hover:shadow-ceramic-hover',
  'transition-[background-color,border-color,box-shadow,opacity] duration-200 ease-in-out',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cable-accent',
);

type ApplicationCardProps = {
  app: {
    avatar?: string;
    title: string;
    update_time: number;
  };
  onClick?(): void;
  moreDropdown: React.ReactNode;
};

export function ApplicationCard({
  app,
  onClick,
  moreDropdown,
}: ApplicationCardProps) {
  return (
    <Card className={applicationCardClass} onClick={onClick} as="article">
      <CardContent className="flex w-full items-center justify-between gap-3 p-0">
        <RAGFlowAvatar
          className="size-12 shrink-0 rounded-xl"
          avatar={app.avatar}
          name={app.title || 'CN'}
          aria-hidden="true"
        />

        <div className="min-w-0 flex-1">
          <h3 className="mb-1 truncate text-sm font-medium text-text-primary">
            {app.title}
          </h3>
          <p className="truncate text-xs text-cable-muted">
            {formatDate(app.update_time)}
          </p>
        </div>

        {moreDropdown}
      </CardContent>
    </Card>
  );
}

export type SeeAllAppCardProps = {
  click(): void;
};

export function SeeAllAppCard({ click }: SeeAllAppCardProps) {
  return (
    <Card
      className={cn(
        applicationCardClass,
        'flex min-h-[76px] items-center justify-center',
      )}
      onClick={click}
      tabIndex={0}
    >
      <CardContent className="flex w-full items-center justify-center gap-1.5 p-0 text-cable-muted transition-colors group-hover:text-cable-brand">
        {t('common.seeAll')} <ChevronRight className="size-4" />
      </CardContent>
    </Card>
  );
}
