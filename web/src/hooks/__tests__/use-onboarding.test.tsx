import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useInvitation, usePasswordRecovery } from '../use-onboarding';

const mockMetadata = jest.fn();
const mockAccept = jest.fn();
const mockReset = jest.fn();
const mockAuthorization = jest.fn();
const mockWorkspace = jest.fn();
jest.mock('@/services/onboarding-service', () => ({
  __esModule: true,
  default: {
    metadata: (...args: unknown[]) => mockMetadata(...args),
    accept: (...args: unknown[]) => mockAccept(...args),
    resetPassword: (...args: unknown[]) => mockReset(...args),
  },
}));
jest.mock('@/utils', () => ({
  rsaPsw: (value: string) => `encrypted:${value}`,
}));
jest.mock('@/utils/authorization-util', () => ({
  __esModule: true,
  default: {
    removeAll: jest.fn(),
    setUserInfo: jest.fn(),
    setAuthorization: (...args: unknown[]) => mockAuthorization(...args),
  },
}));
jest.mock('@/utils/active-tenant', () => ({
  setActiveTenantId: (...args: unknown[]) => mockWorkspace(...args),
}));

const token = 'a'.repeat(32);
function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      {children}
    </QueryClientProvider>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  mockMetadata.mockResolvedValue({
    data: {
      code: 0,
      data: { email: 'new@example.com', tenant_name: 'Team', role: 'normal' },
    },
  });
});

it('reads invitation metadata publicly and persists only the invited workspace on acceptance', async () => {
  mockAccept.mockResolvedValue({
    headers: { authorization: 'signed-auth' },
    data: {
      code: 0,
      data: {
        nickname: 'Member',
        email: 'new@example.com',
        current_tenant_id: 'invited-workspace',
      },
    },
  });
  const { result } = renderHook(() => useInvitation(token), { wrapper });
  await waitFor(() => expect(result.current.metadata.isSuccess).toBe(true));
  expect(mockMetadata).toHaveBeenCalledWith({ token, skipToken: true }, true);
  await act(async () => {
    expect(
      await result.current.accept.mutateAsync({
        nickname: 'Member',
        password: 'test-password',
      }),
    ).toBe(true);
  });
  expect(mockAccept).toHaveBeenCalledWith(
    {
      token,
      skipToken: true,
      data: { nickname: 'Member', password: 'encrypted:test-password' },
    },
    true,
  );
  expect(mockAuthorization).toHaveBeenCalledWith('signed-auth');
  expect(mockWorkspace).toHaveBeenCalledWith('invited-workspace');
});

it('never changes the login session after refused redemption', async () => {
  mockAccept.mockResolvedValue({ data: { code: 108 } });
  const { result } = renderHook(() => useInvitation(token), { wrapper });
  await act(async () => {
    expect(
      await result.current.accept.mutateAsync({
        nickname: 'Member',
        password: 'test-password',
      }),
    ).toBe(false);
  });
  expect(mockAuthorization).not.toHaveBeenCalled();
  expect(mockWorkspace).not.toHaveBeenCalled();
});

it('sends code and encrypted password together when resetting', async () => {
  mockReset.mockResolvedValue({ data: { code: 0 } });
  const { result } = renderHook(() => usePasswordRecovery(), { wrapper });
  await act(async () => {
    await result.current.reset.mutateAsync({
      email: 'member@example.com',
      code: '123456',
      password: 'new-password',
    });
  });
  expect(mockReset).toHaveBeenCalledWith({
    email: 'member@example.com',
    code: '123456',
    newPassword: 'encrypted:new-password',
  });
});
