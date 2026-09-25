import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook } from '@testing-library/react';
import React from 'react';

import { useAddTenantUser } from '../use-user-setting-request';

/**
 * The invite mutation's guards.
 *
 * An invite is sent against the CALLER'S ACTIVE WORKSPACE, so the workspace id
 * has to be in hand before the request is built, and the reply has to be read
 * defensively - a body-less response must not throw inside the mutation, where
 * the rejection would escape the dialog's submit handler.
 */

const mockAddTenantUser = jest.fn();

jest.mock('@/services/user-service', () => ({
  __esModule: true,
  default: { userInfo: jest.fn(), getTenantInfo: jest.fn() },
  addTenantUser: (...args: unknown[]) => mockAddTenantUser(...args),
}));

jest.mock('@/services/knowledge-service', () => ({
  __esModule: true,
  default: { listPipelines: jest.fn() },
}));

jest.mock('@/hooks/use-llm-request', () => ({
  useFetchDefaultModelDictionary: jest.fn(),
}));

jest.mock('@/utils/backend-variant', () => ({
  useIsGoBackend: () => false,
}));

jest.mock('@/locales/config', () => ({
  DEFAULT_LANGUAGE_CODE: 'en',
  supportedLanguages: [{ code: 'en' }],
}));

jest.mock('@/components/ui/message', () => ({
  __esModule: true,
  default: { success: jest.fn(), error: jest.fn(), warning: jest.fn() },
}));

jest.mock('@/utils/active-tenant', () => ({
  getActiveTenantId: () => null,
  setActiveTenantId: jest.fn(),
}));

const makeClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

// `ReturnType<typeof makeClient>` rather than an annotation on the imported
// `QueryClient`: this file needs `jest.mock`, which routes it through the babel
// path of the test transformer, and that path refuses an imported binding used
// in a type annotation.
const makeWrapper =
  (queryClient: ReturnType<typeof makeClient>) =>
  (props: { children?: any }) =>
    React.createElement(
      QueryClientProvider,
      { client: queryClient },
      props.children,
    );

/** Seeds the workspace record the mutation reads, or leaves it unresolved. */
const seedWorkspace = (
  queryClient: ReturnType<typeof makeClient>,
  tenantId: string | undefined,
) => {
  queryClient.setQueryData(['tenantInfo'], { tenant_id: tenantId });
};

describe('invite mutation guards', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('does not send an invite before the workspace record has arrived', async () => {
    const queryClient = makeClient();
    seedWorkspace(queryClient, undefined);

    const { result } = renderHook(() => useAddTenantUser(), {
      wrapper: makeWrapper(queryClient),
    });

    await expect(
      result.current.addTenantUser({ email: 'someone@example.com' }),
    ).resolves.toBeUndefined();
    // `/tenants/undefined/users` is a request that cannot succeed, so none is made.
    expect(mockAddTenantUser).not.toHaveBeenCalled();
  });

  it('survives a reply that carries no body', async () => {
    const queryClient = makeClient();
    seedWorkspace(queryClient, 'tenant-1');
    mockAddTenantUser.mockResolvedValue({ data: undefined });

    const { result } = renderHook(() => useAddTenantUser(), {
      wrapper: makeWrapper(queryClient),
    });

    await expect(
      result.current.addTenantUser({ email: 'someone@example.com' }),
    ).resolves.toBeUndefined();
  });

  it('reports the server code of a refused invite and leaves the roster alone', async () => {
    const queryClient = makeClient();
    seedWorkspace(queryClient, 'tenant-1');
    queryClient.setQueryData(['listTenantUser', 'tenant-1'], []);
    mockAddTenantUser.mockResolvedValue({ data: { code: 102 } });
    const invalidate = jest.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useAddTenantUser(), {
      wrapper: makeWrapper(queryClient),
    });

    await expect(
      result.current.addTenantUser({ email: 'someone@example.com' }),
    ).resolves.toBe(102);
    expect(invalidate).not.toHaveBeenCalled();
    expect(
      queryClient.getQueryState(['listTenantUser', 'tenant-1'])?.isInvalidated,
    ).toBe(false);
  });

  it('invites into the active workspace and re-reads the roster on success', async () => {
    const queryClient = makeClient();
    seedWorkspace(queryClient, 'tenant-1');
    queryClient.setQueryData(['listTenantUser', 'tenant-1'], []);
    mockAddTenantUser.mockResolvedValue({ data: { code: 0 } });

    const { result } = renderHook(() => useAddTenantUser(), {
      wrapper: makeWrapper(queryClient),
    });

    await result.current.addTenantUser({
      email: 'someone@example.com',
      role: 'admin',
      departmentId: 'dept-1',
      title: 'Lead',
    });

    expect(mockAddTenantUser).toHaveBeenCalledWith(
      'tenant-1',
      'someone@example.com',
      'admin',
      { departmentId: 'dept-1', title: 'Lead' },
    );
    expect(
      queryClient.getQueryState(['listTenantUser', 'tenant-1'])?.isInvalidated,
    ).toBe(true);
  });
});
