import { useTranslation } from 'react-i18next';

/**
 * Standard 政企 page footer. It is a normal flow element at the end of the page's
 * own content column — not fixed, not pushed to the viewport bottom — and it is
 * rendered by the page that wants it rather than by the shell, so it does not
 * repeat under every route.
 */
export function AppFooter() {
  const { t } = useTranslation();

  return (
    <footer className="w-full border-t border-border-default bg-bg-base py-8 text-center">
      <p className="text-xs tracking-wide text-text-secondary">
        {t('footer.copyright')}
      </p>
    </footer>
  );
}
