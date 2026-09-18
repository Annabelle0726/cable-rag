import { LanguageAbbreviation } from '@/constants/common';
import i18n from '@/locales/config';
import translation_en from '@/locales/en';
import translation_zh from '@/locales/zh';
import { render, screen } from '@testing-library/react';
import { ChatCardTrailing } from './chat-card-trailing';

// The pill is the only thing a chat card shows at its right edge: the total
// message count. A chat without one leaves that edge empty instead of showing a
// placeholder, and zero counts as no count.
describe('ChatCardTrailing', () => {
  beforeAll(async () => {
    i18n.addResourceBundle(
      LanguageAbbreviation.En,
      'translation',
      translation_en.translation,
    );
    i18n.addResourceBundle(
      LanguageAbbreviation.Zh,
      'translation',
      translation_zh.translation,
    );
  });

  it('shows the message count', async () => {
    await i18n.changeLanguage(LanguageAbbreviation.En);

    render(<ChatCardTrailing messageCount={83} />);

    expect(screen.getByText('83 messages')).toBeInTheDocument();
  });

  it('localises the count label', async () => {
    await i18n.changeLanguage(LanguageAbbreviation.Zh);

    render(<ChatCardTrailing messageCount={14} />);

    expect(screen.getByText('14 条消息')).toBeInTheDocument();
  });

  it('renders nothing for a chat with no messages yet', async () => {
    await i18n.changeLanguage(LanguageAbbreviation.En);

    const { container } = render(<ChatCardTrailing messageCount={0} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the payload carries no count', async () => {
    await i18n.changeLanguage(LanguageAbbreviation.En);

    const { container } = render(<ChatCardTrailing />);

    expect(container).toBeEmptyDOMElement();
  });
});
