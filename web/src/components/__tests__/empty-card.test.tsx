import { EmptyCardType } from '@/components/empty/constant';
import { EmptyAppCard } from '@/components/empty/empty';
import '@/locales/config';
import { render, screen } from '@testing-library/react';

const classList = (element: HTMLElement) => element.className.split(/\s+/);

// The create tiles lost their placeholder sentence, so the tile and its content
// have to hold the centring on their own — no text left to give the layout a
// width to lean on.
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
    // width of its icon once the placeholder text was removed.
    expect(card.className).not.toMatch(
      /md:(items-start|justify-start|text-left|w-fit)/,
    );
  });

  it('groups the icon and the plus so they stay centred together', () => {
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
        'gap-2',
      ]),
    );
    // The business icon plus the plus sign.
    expect(group.children).toHaveLength(2);

    unmount();

    render(<EmptyAppCard type={EmptyCardType.Chat} testId="empty-create-bare" />);

    const bareGroup = screen.getByTestId('empty-create-bare')
      .firstElementChild as HTMLElement;

    // Without the business icon the plus is the only child, still centred.
    expect(bareGroup.children).toHaveLength(1);
    expect(classList(bareGroup)).toEqual(
      expect.arrayContaining(['items-center', 'justify-center']),
    );
  });

  it('renders no placeholder text, while the nothing-matched card keeps its message', () => {
    const { unmount } = render(
      <EmptyAppCard type={EmptyCardType.Chat} testId="empty-create-text" />,
    );

    expect(screen.getByTestId('empty-create-text').textContent?.trim()).toBe('');

    unmount();

    render(
      <EmptyAppCard
        type={EmptyCardType.Chat}
        showIcon
        isSearch
        testId="empty-not-found"
      />,
    );

    expect(
      screen.getByTestId('empty-not-found').textContent?.trim().length,
    ).toBeGreaterThan(0);
  });
});
