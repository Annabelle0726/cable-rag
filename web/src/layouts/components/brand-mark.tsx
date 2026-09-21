import { BrandLogo } from '@/components/brand-logo';
import { cn } from '@/lib/utils';

/**
 * Brand mount point for the header and the mobile navigation sheet.
 *
 * The artwork is a raster mark drawn on white with no alpha channel, so it sits on
 * a white plinth: on the solid 国网绿 bar a bare image would read as a white
 * rectangle floating on the green. The plinth is what makes it look placed rather
 * than pasted, and it keeps the header's 32px rail — the slot the avatars and the
 * controls beside it are built on.
 *
 * The mark is the graphic alone, with no wordmark baked in, so the product name
 * stays real text beside it and remains legible at any density.
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
        'flex h-8 shrink-0 items-center justify-center border border-panel-border bg-white px-1.5',
        className,
      )}
    >
      <BrandLogo alt={label} className="h-4 w-auto" />
    </span>
  );
}
