import { EmptyCardType } from '@/components/empty/constant';
import { EmptyAppCard } from '@/components/empty/empty';
import i18n from '@/locales/config';
import { render, screen } from '@testing-library/react';

const classList = (element: HTMLElement) => element.className.split(/\s+/);

/**
 * The create tiles are the page's only call to action. They have to be the same
 * size as the cards they stand in for — the fixed 112px card — and hold their own
 * centring: an icon, a plus and a one-line prompt on a single row, in the middle
 * of the tile.
 */
describe('empty create card', () => {
  it('keeps a card-sized footprint at every breakpoint', () => {
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
        'h-[112px]',
        'min-h-[112px]',
        'w-full',
      ]),
    );
    // The md-and-up left-aligned, width-to-fit layout collapsed the tile to the
    // width of its icon.
    expect(card.className).not.toMatch(
      /md:(items-start|justify-start|text-left|w-fit)/,
    );
    // No size override of its own any more: the grid cell decides the size.
    expect(card.className).not.toMatch(/max-w-\[480px\]|md:w-\[480px\]|p-14/);
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

  it('keeps the icons and the prompt on one centred row', () => {
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
        'flex-row',
        'flex-wrap',
        'items-center',
        'justify-center',
        'gap-2',
      ]),
    );
    expect(group.className).not.toMatch(/flex-col/);

    // Business icon, plus and prompt, side by side on that one row.
    expect(group.children).toHaveLength(3);

    unmount();

    render(<EmptyAppCard type={EmptyCardType.Chat} testId="empty-create-bare" />);

    const bareGroup = screen.getByTestId('empty-create-bare')
      .firstElementChild as HTMLElement;

    // Without the business icon the plus and the prompt are the row.
    expect(bareGroup.children).toHaveLength(2);
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
