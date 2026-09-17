import { HomeIcon } from '@/components/svg-icon';
import { cn } from '@/lib/utils';
import { PropsWithChildren, ReactNode } from 'react';

/**
 * Home page card grid: one column on phones, two on tablets, three from lg up.
 * Shared so the knowledge-base and application sections stay aligned.
 *
 * Rows are sized `minmax(112px, 1fr)`, which is what makes every card in the
 * section exactly the same size: the floor is one card tall (the card's own
 * padding, title row, description line and date line), the `1fr` makes all rows
 * share the tallest row's height, and the surrounding states — the see-all tile
 * and the dashed create tile — stretch to that same row instead of keeping their
 * own height. A card whose description is empty, or a grid holding nothing but
 * the create tile, therefore matches the full ones instead of sitting shorter.
 */
export function HomeCardGrid({
  children,
  className,
}: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={cn(
        'grid auto-rows-[minmax(112px,1fr)] grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3',
        className,
      )}
    >
      {children}
    </div>
  );
}

type SectionHeadingProps = {
  iconName: string;
  label: string;
  children?: ReactNode;
};

/**
 * Section header: a machined indicator bar, the section icon in a rounded tile
 * and the title, plus an optional right-hand control slot.
 */
export function SectionHeading({
  iconName,
  label,
  children,
}: SectionHeadingProps) {
  return (
    <header className="mb-4 flex min-w-0 items-center justify-between gap-4">
      <h2 className="flex min-w-0 items-center gap-2.5 text-xl font-semibold text-text-primary">
        <span
          aria-hidden
          className="h-4 w-1 shrink-0 rounded-full bg-cable-accent"
        />
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-cable-icon text-cable-icon-foreground">
          <HomeIcon name={iconName} width={18} />
        </span>
        <span className="truncate">{label}</span>
      </h2>
      {children}
    </header>
  );
}
