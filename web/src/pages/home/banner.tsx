import { useTranslation } from 'react-i18next';

/**
 * Home hero: the platform statement shown above the knowledge-base and
 * agent sections. The title uses the theme gradient utility, which resolves
 * per mode from the cable tokens, so no `dark:` variant is needed here.
 *
 * The gradient rides an inline-block span rather than the heading box: the span
 * hugs the text, so the ramp runs across the words instead of stretching over
 * the whole column, and the small bottom padding keeps the clipped background
 * from cropping descenders. Both lines are balanced, and the section closes on
 * the same hairline the cards and the header seam use, not a grey rule.
 */
export function NextBanner() {
  const { t } = useTranslation();

  return (
    <section className="border-b border-cable-hairline pb-8">
      <h1 className="text-4xl leading-[1.2] font-bold tracking-tight md:text-5xl">
        <span className="text-cable-gradient inline-block pb-1">
          {t('header.heroTitle')}
        </span>
      </h1>
      <p className="mt-4 max-w-3xl text-base text-balance text-cable-muted md:text-lg">
        {t('header.heroSubtitle')}
      </p>
    </section>
  );
}
