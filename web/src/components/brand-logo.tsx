import brandLockup from '@/assets/icon/brand-lockup.png';
import brandMark from '@/assets/icon/brand-mark.png';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';

/**
 * The product mark, in the two shapes the console needs.
 *
 * Both are raster crops of the supplied artwork (`芯导logo.jpg`, `芯导logo2.jpg`,
 * which sit beside them untouched): the sources are 2421x1417 sheets with the ink
 * inset in a wide white margin, so `logo.png` and `brand-lockup.png` are the
 * ink alone. Neither has an alpha channel — the artwork is drawn on white — so a
 * caller that puts it on a coloured surface has to give it a light tile, which is
 * what the header mark does.
 *
 * `object-contain` is part of the contract: the slots these land in are square
 * (avatars, icon tiles) and the artwork is wide, so fitting — never filling — is
 * what keeps it undistorted.
 */
export type BrandLogoVariant = 'mark' | 'lockup';

type BrandLogoProps = {
  /**
   * `mark` is the graphic alone, for small slots; `lockup` is the full
   * mark-and-wordmark, for the sign-in column where there is room to read it.
   */
  variant?: BrandLogoVariant;
  className?: string;
  alt?: string;
};

export function BrandLogo({
  variant = 'mark',
  className,
  alt,
}: BrandLogoProps) {
  const { t } = useTranslation();

  return (
    <img
      src={variant === 'lockup' ? brandLockup : brandMark}
      alt={alt ?? t('header.brandShort')}
      className={cn('object-contain', className)}
    />
  );
}
