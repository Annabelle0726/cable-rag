import { cn } from '@/lib/utils';
import { Cable } from 'lucide-react';

/**
 * Brand mount point for the header and the mobile navigation sheet.
 *
 * Deliberately a fixed-size flex slot rather than an image: it keeps the header
 * grid and the nav-overflow measurement stable, so mounting the customer logo
 * later (replace the `<Cable />` mark with the asset) cannot reflow the navbar.
 */
export function BrandMark({
  label,
  className,
}: {
  label: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'flex size-10 shrink-0 items-center justify-center rounded-xl bg-cable-brand-soft text-cable-brand',
        className,
      )}
    >
      <Cable className="size-5" />
      <span className="sr-only">{label}</span>
    </span>
  );
}
