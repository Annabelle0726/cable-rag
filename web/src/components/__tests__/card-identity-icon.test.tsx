import {
  CardIdentityIcon,
  type CardIdentityKind,
} from '@/components/card-identity-icon';
import { fireEvent, render } from '@testing-library/react';

// The chat, search and memory cards used to open each row with the first one or
// two letters of its name on one of four hardcoded saturated gradients. These
// tests pin the replacement: a vector mark per card kind, the owner's image when
// there is one, and no text node either way.
const KINDS: CardIdentityKind[] = ['chat', 'search', 'memory'];

describe('CardIdentityIcon', () => {
  it.each(KINDS)('renders a vector mark for %s, never a name initial', (kind) => {
    const { container } = render(<CardIdentityIcon kind={kind} />);

    // The old fallback rendered the initial as text inside the tile.
    expect(container.textContent).toBe('');
    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(container.querySelector('img')).not.toBeInTheDocument();
  });

  it('renders the owner image instead of the mark when one is set', () => {
    const { container } = render(
      <CardIdentityIcon kind="chat" avatar="https://example.test/a.png" />,
    );

    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      'https://example.test/a.png',
    );
    expect(container.querySelector('svg')).not.toBeInTheDocument();
  });

  it('degrades to the vector mark when the image fails to load', () => {
    const { container } = render(
      <CardIdentityIcon kind="memory" avatar="https://example.test/broken.png" />,
    );

    fireEvent.error(container.querySelector('img') as HTMLImageElement);

    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(container.querySelector('img')).not.toBeInTheDocument();
  });
});
