import SvgIcon from '@/components/svg-icon';
import { cn } from '@/lib/utils';

/**
 * Brand mount point for the header and the mobile navigation sheet.
 *
 * Renders the shared brand logo asset, the same one the assistant falls back to
 * for its avatar, so the product mark exists in exactly one file
 * (`assets/svg/brand-logo.svg`). A fixed-size flex slot rather than a
 * text-flowing logo keeps the header grid and the nav-overflow measurement
 * stable when the artwork changes.
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
        'flex size-10 shrink-0 items-center justify-center rounded-xl bg-cable-brand-soft',
        className,
      )}
    >
      <SvgIcon name="brand-logo" width={24} height={24} />
      <span className="sr-only">{label}</span>
    </span>
  );
}
