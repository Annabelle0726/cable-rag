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
 *
 * The artwork fills only about three quarters of its own 24-unit viewBox, so the
 * render size is the slot's 32px rather than 24px: at 24px the drawn mark came
 * out around 18x12px in a 32px box, which read as a mark floating in a slot
 * twice its size next to the 32px avatars elsewhere in the header.
 *
 * The slot carries no surface of its own: the mark and the wordmark sit in the
 * one capsule their parent draws, so the header does not read as a box inside a
 * box. The glow class is what lights the mark when that capsule is hovered.
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
        'flex size-8 shrink-0 items-center justify-center',
        className,
      )}
    >
      <SvgIcon
        name="brand-logo"
        width={32}
        height={32}
        imgClass="brand-entry-mark"
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
