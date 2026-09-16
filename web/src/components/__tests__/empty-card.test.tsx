import { EmptyCardType } from '@/components/empty/constant';
import { EmptyAppCard } from '@/components/empty/empty';
import i18n from '@/locales/config';
import { render, screen } from '@testing-library/react';

const classList = (element: HTMLElement) => element.className.split(/\s+/);

/**
 * The create tiles are the page's only call to action, so they have to hold
 * their own centring: an icon, a plus and a one-line prompt, stacked in the
 * middle of a tile that keeps a standard size.
 */
describe('empty create card', () => {
  it('centres the tile and its content at every breakpoint', () => {
    render(
      <EmptyAppCard type={EmptyCardType.Chat} showIcon testId="empty-create" />,
    );

    const card = screen.getByTestId('empty-create');

    expect(classList(card)).toEqual(
      expect.arrayContaining([
        'flex',
        'flex-col',
        'items-center',
        'justify-center',
        'min-h-[160px]',
      ]),
    );
    // The md-and-up left-aligned, width-to-fit layout collapsed the tile to the
    // width of its icon.
    expect(card.className).not.toMatch(
      /md:(items-start|justify-start|text-left|w-fit)/,
    );
  });

  it('reads as a button on hover', () => {
    render(
      <EmptyAppCard type={EmptyCardType.Dataset} testId="empty-hover" />,
    );

    const card = screen.getByTestId('empty-hover');

    expect(card.className).toMatch(/hover:border-accent-color/);
    expect(card.className).toMatch(/hover:shadow-accent-glow/);
    expect(card.className).toMatch(/duration-200/);
  });

  it('stacks the icons and the prompt as one centred group', () => {
    const { unmount } = render(
      <EmptyAppCard
        type={EmptyCardType.Dataset}
        showIcon
        testId="empty-create-icon"
      />,
    );

    const group = screen.getByTestId('empty-create-icon')
      .firstElementChild as HTMLElement;

    expect(classList(group)).toEqual(
      expect.arrayContaining([
        'flex',
        'flex-col',
        'items-center',
        'justify-center',
        'gap-3',
      ]),
    );

    // The business icon and the plus, then the prompt: two blocks, and the icons
    // are spaced apart inside their own stack.
    expect(group.children).toHaveLength(2);

    const icons = group.firstElementChild as HTMLElement;

    expect(classList(icons)).toEqual(
      expect.arrayContaining(['flex', 'flex-col', 'items-center', 'gap-2']),
    );
    expect(icons.children).toHaveLength(2);

    unmount();

    render(<EmptyAppCard type={EmptyCardType.Chat} testId="empty-create-bare" />);

    const bareIcons = screen.getByTestId('empty-create-bare')
      .firstElementChild?.firstElementChild as HTMLElement;

    // Without the business icon the plus is the only child, still centred.
    expect(bareIcons.children).toHaveLength(1);
  });

  it('states the action, and reports the empty result on the search card', () => {
    const { unmount } = render(
      <EmptyAppCard type={EmptyCardType.Chat} testId="empty-create-text" />,
    );

    expect(screen.getByTestId('empty-create-text')).toHaveTextContent(
      i18n.t('empty.chatTitle'),
    );

    unmount();

    render(
      <EmptyAppCard
        type={EmptyCardType.Chat}
        showIcon
        isSearch
        testId="empty-not-found"
      />,
    );

    expect(screen.getByTestId('empty-not-found')).toHaveTextContent(
      i18n.t('empty.notFoundChat'),
    );
  });
});
