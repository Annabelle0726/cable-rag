import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AddingUserModal from '../add-user-modal';

const hideModal = jest.fn();

jest.mock('@/hooks/use-user-setting-request', () => ({
  useListDepartments: () => ({
    data: [{ id: 'dept-1', name: 'Grid Ops' }],
    loading: false,
  }),
}));

// jsdom implements neither pointer capture nor scrollIntoView, and Radix's
// Select calls both on pointerdown and on option focus.
beforeAll(() => {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
  Element.prototype.scrollIntoView = () => {};
});

/**
 * The invite dialog's two pickers, driven the way a pointer drives them.
 *
 * `userEvent` fires the pointerdown/mousedown/pointerup/mouseup/click sequence
 * Radix listens to, which `fireEvent.click` does not - and it is that sequence
 * which decides whether the dialog treats an interaction with a popup portalled
 * to `document.body` as an "outside" one and dismisses itself. Choosing a role
 * or a department must therefore leave the dialog open, and must apply.
 */
describe('invite dialog pickers', () => {
  beforeEach(() => {
    hideModal.mockClear();
  });

  const renderDialog = async () => {
    render(
      <AddingUserModal
        visible
        hideModal={hideModal}
        loading={false}
        onOk={jest.fn()}
      />,
    );
    const dialog = await screen.findByRole('dialog');
    return {
      dialog,
      // The role picker is the first combobox; the department one has a testid.
      roleTrigger: within(dialog).getAllByRole('combobox')[0],
      departmentTrigger: within(dialog).getByTestId('invite-department'),
    };
  };

  it('applies the role without closing the dialog', async () => {
    const user = userEvent.setup();
    const { roleTrigger } = await renderDialog();

    await user.click(roleTrigger);
    await user.click(await screen.findByRole('option', { name: 'Admin' }));

    // The choice landed on the field, and the dialog is still up with it.
    await waitFor(() => {
      expect(roleTrigger).toHaveTextContent('Admin');
    });
    expect(screen.queryByRole('dialog')).not.toBeNull();
    expect(hideModal).not.toHaveBeenCalled();
  });

  it('applies the department without closing the dialog', async () => {
    const user = userEvent.setup();
    const { departmentTrigger } = await renderDialog();

    await user.click(departmentTrigger);
    await user.click(await screen.findByRole('option', { name: 'Grid Ops' }));

    await waitFor(() => {
      expect(departmentTrigger).toHaveTextContent('Grid Ops');
    });
    expect(screen.queryByRole('dialog')).not.toBeNull();
    expect(hideModal).not.toHaveBeenCalled();
  });

  it('labels the role field as a role, not a status', async () => {
    const { dialog } = await renderDialog();

    // `setting.role` is the field's label and both roster headers'; it must not
    // read "status" while the choices are member/admin.
    expect(within(dialog).getByText('Role')).toBeInTheDocument();
    expect(within(dialog).queryByText('State')).toBeNull();
  });

  it('Escape closes only the role popup before closing the parent dialog', async () => {
    const user = userEvent.setup();
    const { roleTrigger } = await renderDialog();
    await user.click(roleTrigger);
    expect(await screen.findByRole('listbox')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(hideModal).not.toHaveBeenCalled();
    await user.keyboard('{Escape}');
    expect(hideModal).toHaveBeenCalledTimes(1);
  });
});
