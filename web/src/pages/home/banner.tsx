import { useTranslation } from 'react-i18next';

/**
 * Home hero: the platform statement shown above the knowledge-base and
 * agent sections. The title uses the theme gradient utility, which resolves
 * per mode from the cable tokens, so no `dark:` variant is needed here. The
 * blueprint micro-grid behind it is the same CAD lattice the glass panes carry,
 * at 3-5%: enough to read as a drawing sheet, faint enough to stay behind the
 * headline.
 */
export function NextBanner() {
  const { t } = useTranslation();

  return (
    <section className="blueprint-grid border-b border-cable-divider pb-8">
      <h1 className="text-4xl leading-tight font-bold tracking-tight md:text-5xl">
        <span className="text-cable-gradient">{t('header.heroTitle')}</span>
      </h1>
      <p className="mt-4 max-w-3xl text-base text-cable-muted md:text-lg">
        {t('header.heroSubtitle')}
      </p>
    </section>
  );
}
