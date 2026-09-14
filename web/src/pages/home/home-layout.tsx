import { HomeIcon } from '@/components/svg-icon';
import { cn } from '@/lib/utils';
import { PropsWithChildren, ReactNode } from 'react';

/**
 * Home page card grid: one column on phones, two on tablets, three from lg up.
 * Shared so the knowledge-base and application sections stay aligned.
 */
export function HomeCardGrid({
  children,
  className,
}: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3',
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
