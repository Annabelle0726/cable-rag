import brandLockup from '@/assets/icon/brand-lockup.png';
import brandMark from '@/assets/icon/brand-mark.png';
import brandPoster from '@/assets/icon/brand-poster.jpg';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';

/**
 * The product mark, in the three shapes the console needs.
 *
 * `brand-mark.png` and `brand-lockup.png` are the assets rendered from the
 * supplied artwork (`芯导logo.jpg`, which sits beside them untouched) and
 * `brand-poster.jpg` is its tall companion (`芯导logo2.jpg`) — all three are no
 * wider than the artwork itself, so a slot that is square or rail-height has to
 * fit rather than fill them.
 *
 * `object-contain` is part of the contract: the slots these land in are square
 * (avatars, icon tiles) or short rails, so fitting — never filling — is what
 * keeps the artwork undistorted. The artwork is drawn on white, so a caller that
 * puts it on a coloured surface has to give it a light tile, which is what the
 * app bar does.
 */
export type BrandLogoVariant = 'mark' | 'lockup' | 'poster';

const brandSources: Record<BrandLogoVariant, string> = {
  mark: brandMark,
  lockup: brandLockup,
  poster: brandPoster,
};

type BrandLogoProps = {
  /**
   * `mark` is the graphic alone, for small slots; `lockup` is the wide
   * mark-and-wordmark, for the app bar; `poster` is the tall artwork, for the
   * sign-in column where there is room to read it.
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
      src={brandSources[variant]}
      alt={alt ?? t('header.brandShort')}
      className={cn('object-contain', className)}
    />
  );
}
