import { RAGFlowPagination } from '@/components/ui/ragflow-pagination';
import { LanguageAbbreviation } from '@/constants/common';
import i18n from '@/locales/config';
import translation_en from '@/locales/en';
import translation_zh from '@/locales/zh';
import { render, screen } from '@testing-library/react';

// The footer used to render the raw keys `pagination.total` / `pagination.page`
// because neither locale defined the section at all.
//
// jest cannot resolve the lazy `import('./zh')` the app relies on (it needs
// --experimental-vm-modules), so both bundles are registered here by hand. The
// strings under test are still the real ones from the locale files.
const registerBundle = async (
  lng: string,
  bundle: { translation: object },
): Promise<void> => {
  i18n.addResourceBundle(lng, 'translation', bundle.translation);
  await i18n.changeLanguage(lng);
};

describe('pagination labels', () => {
  beforeEach(async () => {
    await registerBundle(LanguageAbbreviation.En, translation_en);
    await registerBundle(LanguageAbbreviation.Zh, translation_zh);
  });

  it('renders the row count in Chinese instead of the key', async () => {
    await i18n.changeLanguage(LanguageAbbreviation.Zh);

    render(<RAGFlowPagination total={12} current={1} pageSize={10} />);

    expect(await screen.findByText('共 12 条')).toBeInTheDocument();
    expect(screen.queryByText(/pagination\./)).not.toBeInTheDocument();
  });

  it('renders the row count in English instead of the key', async () => {
    await i18n.changeLanguage(LanguageAbbreviation.En);

    render(<RAGFlowPagination total={12} current={1} pageSize={10} />);

    expect(await screen.findByText('Total 12')).toBeInTheDocument();
    expect(screen.queryByText(/pagination\./)).not.toBeInTheDocument();
  });

  it('labels a page-size option with the size, not the page number', async () => {
    await i18n.changeLanguage(LanguageAbbreviation.Zh);
    expect(i18n.t('pagination.page', { size: 20 })).toBe('20 条/页');

    await i18n.changeLanguage(LanguageAbbreviation.En);
    expect(i18n.t('pagination.page', { size: 20 })).toBe('20/page');
  });
});
