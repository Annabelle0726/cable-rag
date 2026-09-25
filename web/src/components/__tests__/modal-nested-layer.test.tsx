import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Modal } from '../ui/modal/modal';

const onOpenChange = jest.fn();

beforeEach(() => onOpenChange.mockClear());

it.each(['listbox', 'viewport'])(
  'keeps the dialog open for a portalled Select %s',
  async (kind) => {
    render(
      <Modal open title="Invite" onOpenChange={onOpenChange}>
        <input aria-label="Email" />
      </Modal>,
    );
    const popup = document.createElement('div');
    if (kind === 'listbox') popup.setAttribute('role', 'listbox');
    else popup.setAttribute('data-radix-select-viewport', '');
    popup.style.pointerEvents = 'auto';
    const option = document.createElement('button');
    option.textContent = 'Nested option';
    popup.appendChild(option);
    document.body.appendChild(popup);
    try {
      await userEvent.setup().click(option);
      expect(onOpenChange).not.toHaveBeenCalled();
    } finally {
      popup.remove();
    }
  },
);

it.each([true, false])(
  'honors maskClosable=%s for a genuine backdrop click',
  async (maskClosable) => {
    render(
      <Modal
        open
        title="Invite"
        maskClosable={maskClosable}
        onOpenChange={onOpenChange}
      >
        <input aria-label="Email" />
      </Modal>,
    );
    const overlay = screen.getByRole('dialog').parentElement!;
    await userEvent.setup().click(overlay);
    if (maskClosable) expect(onOpenChange).toHaveBeenCalledWith(false);
    else expect(onOpenChange).not.toHaveBeenCalled();
  },
);

it('closes once on Escape when no nested layer is open', async () => {
  render(
    <Modal open title="Invite" onOpenChange={onOpenChange}>
      <input aria-label="Email" />
    </Modal>,
  );
  await userEvent.setup().keyboard('{Escape}');
  expect(onOpenChange).toHaveBeenCalledTimes(1);
  expect(onOpenChange).toHaveBeenCalledWith(false);
});
