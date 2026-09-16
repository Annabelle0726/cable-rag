import { SettingsDrawer } from '@/components/settings-drawer';
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';

function Harness() {
  const [open, setOpen] = useState(true);

  return (
    <SettingsDrawer
      open={open}
      onOpenChange={setOpen}
      title="聊天设置"
      testId="chat-detail-settings"
      footer={<button type="button">save</button>}
    >
      <p>retrieval</p>
    </SettingsDrawer>
  );
}

const getPanel = () => screen.getByTestId('chat-detail-settings');

describe('SettingsDrawer', () => {
  it('slides in from the right at the requested width', () => {
    render(<Harness />);

    const panel = getPanel();
    // 480px on a normal viewport, 80vw on a narrow one, anchored to the right.
    expect(panel.className).toContain('sm:w-[480px]');
    expect(panel.className).toContain('max-w-[80vw]');
    expect(panel.className).toContain('inset-y-0');
    expect(panel.className).toContain('right-0');
    expect(panel.className).toContain('slide-in-from-right');
    // The panel casts leftwards over the conversation.
    expect(panel.className).toContain('shadow-cable-drawer');
    // Viewport anchored by default: the chat page lets the drawer cover its own
    // header.
    expect(panel.className).toContain('fixed');
    expect(panel.className).not.toContain('absolute');
  });

  it('anchors to its own container when the page asks for it', () => {
    render(
      <div className="relative">
        <SettingsDrawer
          open
          onOpenChange={() => {}}
          title="搜索设置"
          testId="search-settings-drawer"
          contained
        >
          <p>kb</p>
        </SettingsDrawer>
      </div>,
    );

    const panel = screen.getByTestId('search-settings-drawer');

    // `absolute` is what keeps the panel and its backdrop below the app bar.
    expect(panel.className).toContain('absolute');
    expect(panel.className).not.toContain('fixed');
    expect(
      document.querySelector('[data-state="open"].bg-cable-backdrop')
        ?.className,
    ).toContain('absolute');
  });

  it('scrolls its body so every setting stays reachable', () => {
    render(<Harness />);

    expect(screen.getByTestId('chat-detail-settings-body').className).toContain(
      'overflow-y-auto',
    );
  });

  it('dims the chat behind it instead of hiding it', () => {
    render(<Harness />);

    const overlay = document.querySelector(
      '[data-state="open"].bg-cable-backdrop',
    );
    expect(overlay).not.toBeNull();
    // A light backdrop keeps the conversation readable behind the drawer.
    expect(overlay?.className).not.toContain('bg-black/80');
  });

  it('closes from the close button', () => {
    render(<Harness />);

    fireEvent.click(screen.getByTestId('chat-detail-settings-close'));

    expect(screen.queryByTestId('chat-detail-settings')).toBeNull();
  });

  it('closes on Escape', () => {
    render(<Harness />);

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(screen.queryByTestId('chat-detail-settings')).toBeNull();
  });
});
