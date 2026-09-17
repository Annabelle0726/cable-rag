import { useTranslation } from 'react-i18next';

/**
 * Home hero: the platform statement shown above the knowledge-base and
 * agent sections. The title uses the theme gradient utility, which resolves
 * per mode from the cable tokens, so no `dark:` variant is needed here.
 *
 * The gradient rides an inline-block span rather than the heading box: the span
 * hugs the text, so the ramp runs across the words instead of stretching over
 * the whole column. A clipped background only paints the span's own box, so the
 * span carries vertical padding and a roomy line box — at a tight line height
 * the taller CJK glyphs reach past the box and lose their fill, which is what
 * made the heading look like it overflowed. The subtitle takes its colour from
 * the semantic content scale rather than a grey picked here.
 */
export function NextBanner() {
  const { t } = useTranslation();

  return (
    <section className="border-b border-cable-hairline pb-8">
      <h1 className="max-w-4xl text-2xl leading-snug font-bold tracking-tight sm:text-3xl md:text-4xl">
        <span className="text-cable-gradient inline-block max-w-full py-1">
          {t('header.heroTitle')}
        </span>
      </h1>
      <p className="mt-3 max-w-3xl text-base text-balance text-content-secondary md:text-lg">
        {t('header.heroSubtitle')}
      </p>
    </section>
  );
}
