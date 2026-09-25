import { act, renderHook } from '@testing-library/react';

import { useAddUser } from '../hooks';

/**
 * The invite dialog's submit handler must never reject.
 *
 * A refused invite resolves with a non-zero code (the request layer has already
 * toasted the server's message), but a transport failure REJECTS. Since this
 * handler is what the dialog's confirm button awaits, an escaping rejection is
 * what turns a failed invitation into a broken page instead of a dialog that
 * stays open with the typed address still in it.
 */

const mockAddTenantUser = jest.fn();
const mockHideModal = jest.fn();

jest.mock('@/hooks/use-user-setting-request', () => ({
  useAddTenantUser: () => ({ addTenantUser: mockAddTenantUser }),
  useAgreeTenant: () => ({ agreeTenant: jest.fn() }),
  useDeleteTenantUser: () => ({ deleteTenantUser: jest.fn() }),
  useFetchUserInfo: () => ({ data: {} }),
}));

jest.mock('@/hooks/common-hooks', () => ({
  useSetModalState: () => ({
    visible: true,
    hideModal: mockHideModal,
    showModal: jest.fn(),
  }),
  useShowDeleteConfirm: () => jest.fn(),
}));

describe('invite submit', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('closes the dialog when the invitation is accepted', async () => {
    mockAddTenantUser.mockResolvedValue(0);
    const { result } = renderHook(() => useAddUser());

    await act(async () => {
      await result.current.handleAddUserOk({ email: 'someone@example.com' });
    });

    expect(mockHideModal).toHaveBeenCalledTimes(1);
  });

  it('keeps the dialog open, and does not reject, when the server refuses', async () => {
    mockAddTenantUser.mockResolvedValue(102);
    const { result } = renderHook(() => useAddUser());

    await act(async () => {
      await result.current.handleAddUserOk({ email: 'someone@example.com' });
    });

    expect(mockHideModal).not.toHaveBeenCalled();
  });

  it('swallows a transport failure instead of letting it escape', async () => {
    mockAddTenantUser.mockRejectedValue(new Error('request failed'));
    const { result } = renderHook(() => useAddUser());

    // The assertion is that this resolves at all: before the catch, the
    // rejection reached the caller as an unhandled rejection.
    await expect(
      act(async () => {
        await result.current.handleAddUserOk({ email: 'someone@example.com' });
      }),
    ).resolves.toBeUndefined();
    expect(mockHideModal).not.toHaveBeenCalled();
  });
});
