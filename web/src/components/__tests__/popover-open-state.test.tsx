import { Popover } from '@/components/ui/popover';
import { render } from '@testing-library/react';

// Radix is the only thing that sees the wrapper's internal open state, and that
// state is what decides whether the panel paints before the sync effect runs.
// Recording it here catches the first-commit value that a page load used to
// flash open.
const mockOpenHistory: boolean[] = [];

jest.mock('@radix-ui/react-popover', () => ({
  Root: ({ open }: { open?: boolean }) => {
    mockOpenHistory.push(!!open);
    return null;
  },
  Trigger: () => null,
  Portal: ({ children }: { children?: unknown }) => children,
  // The wrapper reads `Content.displayName` at module scope.
  Content: Object.assign(() => null, { displayName: 'PopoverContent' }),
}));

describe('Popover', () => {
  it('starts closed when the caller controls it closed', () => {
    mockOpenHistory.length = 0;

    render(
      <Popover open={false}>
        <span />
      </Popover>,
    );

    expect(mockOpenHistory[0]).toBe(false);
  });

  it('starts closed when it is uncontrolled', () => {
    mockOpenHistory.length = 0;

    render(
      <Popover>
        <span />
      </Popover>,
    );

    expect(mockOpenHistory[0]).toBe(false);
  });

  it('starts open when the caller controls it open', () => {
    mockOpenHistory.length = 0;

    render(
      <Popover open>
        <span />
      </Popover>,
    );

    expect(mockOpenHistory[0]).toBe(true);
  });
});
