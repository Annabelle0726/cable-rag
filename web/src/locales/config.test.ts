import i18n, {
  DEFAULT_LANGUAGE_CODE,
  changeLanguageAsync,
  initLanguage,
  supportedLanguages,
} from './config';

const LanguageStorageKey = 'lng';

describe('language configuration', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('lists Simplified Chinese first and English second', () => {
    expect(supportedLanguages.map((x) => x.code)).toEqual(['zh-Hans', 'en']);
    expect(supportedLanguages.map((x) => x.displayName)).toEqual([
      '简体中文',
      'English',
    ]);
  });

  it('defaults to Simplified Chinese', () => {
    expect(DEFAULT_LANGUAGE_CODE).toBe('zh-Hans');
  });

  it('writes the default on a first visit and keeps a saved choice', async () => {
    await initLanguage();
    expect(window.localStorage.getItem(LanguageStorageKey)).toBe('zh-Hans');

    window.localStorage.setItem(LanguageStorageKey, 'en');
    await initLanguage();
    expect(window.localStorage.getItem(LanguageStorageKey)).toBe('en');
  });

  it.each(['zh', 'zh_CN', 'zh-CN'])(
    'normalises the stored tag %s to the bundled Simplified Chinese code',
    async (lng) => {
      await changeLanguageAsync(lng);

      expect(window.localStorage.getItem(LanguageStorageKey)).toBe('zh-Hans');
    },
  );

  describe('a key that no bundle defines', () => {
    beforeEach(async () => {
      await changeLanguageAsync('en');
    });

    it('never reaches the screen as module.keyName', () => {
      expect(i18n.t('search.searchAppsThatDoNotExist')).toBe(
        'Search apps that do not exist',
      );
      expect(i18n.t('module.keyName')).not.toBe('module.keyName');
    });

    it('still yields to an inline default value', () => {
      expect(i18n.t('module.keyName', 'Something concrete')).toBe(
        'Something concrete',
      );
    });
  });
});
