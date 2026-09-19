import ThemeSwitch from '@/components/theme-switch';
import { render, screen } from '@testing-library/react';

const mockTheme = { isDark: false };

jest.mock('@/components/theme-provider', () => ({
  useTheme: () => ({ setTheme: jest.fn() }),
  useIsDarkTheme: () => mockTheme.isDark,
}));

const renderSwitch = (isDark: boolean) => {
  mockTheme.isDark = isDark;

  render(<ThemeSwitch />);

  const track = screen.getByRole('switch');

  return {
    track,
    thumb: track.querySelector('.ceramic-switch-thumb') as HTMLElement,
    icons: Array.from(track.querySelectorAll('svg')),
  };
};

// The switch used to be a flat grey box with a white-or-black slider, which read
// as a different material from the toolbars it sits next to.
describe('theme switch', () => {
  it('dresses the track as a ceramic recess instead of a flat grey box', () => {
    const { track } = renderSwitch(false);

    expect(track.className).toMatch(/ceramic-switch/);
    expect(track.className).toMatch(/rounded-full/);
    // The ink-filled/plain-card surfaces the primitive family would bring.
    expect(track.className).not.toMatch(/bg-bg-card|bg-bg-base|bg-black/);
  });

  it('lifts a brand slider that slides over 300ms', () => {
    const { thumb } = renderSwitch(false);

    expect(thumb).not.toBeNull();
    expect(thumb.className).toMatch(/ceramic-switch-thumb/);
    expect(thumb.className).not.toMatch(/bg-bg-base|bg-bg-card|bg-black/);
    // The moving wrapper, not the visual: it is what carries the translation.
    expect(thumb.parentElement?.className).toMatch(
      /transition-all duration-300 ease-in-out/,
    );
    expect(thumb.parentElement?.className).not.toMatch(/ease-out/);
  });

  it('inks the selected icon on the accent and idles the other one', () => {
    const light = renderSwitch(false);

    expect(light.icons).toHaveLength(2);
    // Sun first, moon second: light mode selects the sun.
    expect(light.icons[0].getAttribute('class')).toMatch(/text-accent-contrast/);
    // Colour alone carries the state: no glow on either icon.
    expect(light.icons[0].getAttribute('class')).not.toMatch(/drop-shadow/);
    expect(light.icons[1].getAttribute('class')).toMatch(/text-text-secondary/);
    expect(light.icons[1].getAttribute('class')).not.toMatch(
      /text-accent-contrast/,
    );
  });

  it('moves the selection to the moon in dark mode', () => {
    const dark = renderSwitch(true);

    expect(dark.icons[0].getAttribute('class')).toMatch(/text-text-secondary/);
    expect(dark.icons[1].getAttribute('class')).toMatch(
      /text-accent-contrast/,
    );
  });
});
