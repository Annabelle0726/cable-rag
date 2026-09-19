import { render, screen } from '@testing-library/react';
import { RAGFlowAvatar, getAvatarInitial } from '../ragflow-avatar';

// Radix renders its image element only once the browser reports the URL as
// loaded, which never happens under jsdom. Stubbing the primitive keeps the
// real Avatar/AvatarFallback behaviour while letting the priority-1 wiring be
// asserted.
jest.mock('@/components/ui/avatar', () => {
  const actual = jest.requireActual('@/components/ui/avatar');

  return {
    ...actual,
    AvatarImage: ({ src }: { src?: string }) =>
      src ? <img src={src} alt="" /> : null,
  };
});

describe('getAvatarInitial', () => {
  it('takes the first character of the first candidate that holds text', () => {
    expect(getAvatarInitial('zhang wei', 'zhang@example.com')).toBe('Z');
    expect(getAvatarInitial('', 'zhang@example.com')).toBe('Z');
    expect(getAvatarInitial(undefined, 'zhang@example.com')).toBe('Z');
    expect(getAvatarInitial('  ', '  zhang@example.com  ')).toBe('Z');
  });

  it('keeps a single character for a name that has no spaces', () => {
    expect(getAvatarInitial('cable', 'cable@example.com')).toBe('C');
    expect(getAvatarInitial('张伟')).toBe('张');
  });

  it('does not split a surrogate pair', () => {
    expect(getAvatarInitial('😀 cable')).toBe('😀');
  });

  it('returns nothing when there is no name at all', () => {
    expect(getAvatarInitial()).toBe('');
    expect(getAvatarInitial(undefined, '')).toBe('');
  });
});

describe('RAGFlowAvatar', () => {
  it('shows the uploaded image when there is one', () => {
    render(
      <RAGFlowAvatar
        name="zhang wei"
        email="zhang@example.com"
        avatar="/avatar.png"
        isPerson
      />,
    );

    expect(document.querySelector('img')?.getAttribute('src')).toBe(
      '/avatar.png',
    );
  });

  it('asks for no image when the avatar is empty', () => {
    render(<RAGFlowAvatar name="zhang wei" avatar="" isPerson />);

    expect(document.querySelector('img')).toBeNull();
  });

  it('falls back to the uppercased initial on the brand surface', () => {
    render(
      <RAGFlowAvatar name="zhang wei" email="zhang@example.com" isPerson />,
    );

    const fallback = screen.getByTestId('avatar-fallback');
    expect(fallback.textContent).toBe('Z');
    expect(fallback.className).toContain('bg-cable-avatar');
    expect(fallback.className).toContain('text-cable-avatar-foreground');
  });

  it('falls back to the email initial when the nickname is empty', () => {
    render(<RAGFlowAvatar name="" email="engineer@cable.example" isPerson />);

    expect(screen.getByTestId('avatar-fallback').textContent).toBe('E');
  });

  it('renders a neutral glyph when there is nothing to initialise from', () => {
    render(<RAGFlowAvatar isPerson />);

    const fallback = screen.getByTestId('avatar-fallback');
    expect(fallback.textContent).toBe('');
    expect(fallback.querySelector('svg')).not.toBeNull();
  });

  it('keeps the two-letter fallback for non-person avatars on the neutral surface', () => {
    render(<RAGFlowAvatar name="Cable Assistant" />);

    const fallback = screen.getByTestId('avatar-fallback');
    expect(fallback.textContent).toBe('CA');
    // A machine entity reads as a framed grey tile; only a person takes the brand
    // fill. No per-name gradient.
    expect(fallback.className).toContain('bg-bg-title');
    expect(fallback.className).not.toContain('bg-cable-avatar');
    expect(fallback.style.backgroundImage).toBe('');
  });
});
