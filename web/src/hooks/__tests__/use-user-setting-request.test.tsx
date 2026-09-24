/*
 *  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';

import {
  useAddTenantUser,
  useAgreeTenant,
  useDeleteTenantUser,
  useListTenantUser,
  useUpdateTenantUserRole,
} from '../use-user-setting-request';

/**
 * The team-page mutations' effects on the cache and on the stored active
 * workspace.
 *
 * A role change or a removal leaves the roster stale, and accepting an
 * invitation also switches the active workspace server-side - so the roster has
 * to be re-keyed onto the new workspace instead of staying cached under the old
 * one. These tests pin both the invalidation and the `X-Tenant-Id` value the
 * next request will carry.
 */

let mockCallerId = 'user-1';
let mockActiveTenantId: string | null = 'tenant-1';

const mockAddTenantUser = jest.fn();
const mockDeleteTenantUser = jest.fn();
const mockUpdateTenantUserRole = jest.fn();
const mockAgreeTenant = jest.fn();
const mockSetActiveTenantId = jest.fn();

jest.mock('@/services/user-service', () => ({
  __esModule: true,
  default: {
    userInfo: jest.fn(),
    getTenantInfo: jest.fn(),
  },
  addTenantUser: (...args: unknown[]) => mockAddTenantUser(...args),
  deleteTenantUser: (...args: unknown[]) => mockDeleteTenantUser(...args),
  updateTenantUserRole: (...args: unknown[]) =>
    mockUpdateTenantUserRole(...args),
  agreeTenant: (...args: unknown[]) => mockAgreeTenant(...args),
  listTenantUser: jest.fn(),
  listTenant: jest.fn(),
  listDepartments: jest.fn(),
  setActiveTenant: jest.fn(),
  updateTenantUserProfile: jest.fn(),
  createDepartment: jest.fn(),
  renameDepartment: jest.fn(),
  deleteDepartment: jest.fn(),
}));

// The service layer is mocked, so nothing here should reach the request stack;
// the knowledge and llm modules are stubbed only to keep this test's module
// graph small.
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
  getActiveTenantId: () => mockActiveTenantId,
  setActiveTenantId: (...args: unknown[]) => mockSetActiveTenantId(...args),
}));

/** The roster key the read hook uses, which an invalidation must also name. */
const ROSTER_KEY = ['listTenantUser', 'tenant-1'] as const;
const TENANT_LIST_KEY = ['listTenant'] as const;

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
}

// `ReturnType<typeof makeClient>` rather than an annotation on the imported
// `QueryClient`: this file needs a `jest.mock`, which routes it through the
// babel path of the test transformer, and that path refuses an imported binding
// used in a type annotation.
function makeWrapper(queryClient: ReturnType<typeof makeClient>) {
  // Built with createElement so the wrapper needs no JSX-specific typing.
  const Wrapper = (props: { children?: any }) =>
    React.createElement(
      QueryClientProvider,
      { client: queryClient },
      props.children,
    );

  return Wrapper;
}

/**
 * Seeds the cache the way a successful read would, so invalidation is
 * observable and the mutations see the caller and the active workspace without
 * waiting on a round trip.
 */
function seedActiveWorkspaceCaches(queryClient: ReturnType<typeof makeClient>) {
  queryClient.setQueryData(['userInfo'], { id: mockCallerId, role: 'normal' });
  queryClient.setQueryData(['tenantInfo'], {
    tenant_id: 'tenant-1',
    name: 'Cable Works',
  });
  queryClient.setQueryData(ROSTER_KEY, [{ user_id: 'user-2', role: 'normal' }]);
  queryClient.setQueryData(TENANT_LIST_KEY, [{ tenant_id: 'tenant-1' }]);
}

const isInvalidated = (
  queryClient: ReturnType<typeof makeClient>,
  key: readonly unknown[],
) => queryClient.getQueryState(key)?.isInvalidated ?? false;

/**
 * The caller's own account and active workspace, which the mutations read to
 * tell "removed a member" from "left the workspace I am in".
 */
function currentUserService() {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const service = jest.requireMock('@/services/user-service').default;
  (service.userInfo as jest.Mock).mockResolvedValue({
    data: {
      code: 0,
      data: { id: mockCallerId, nickname: 'Ann Member', role: 'normal' },
    },
  });
  (service.getTenantInfo as jest.Mock).mockResolvedValue({
    data: {
      code: 0,
      data: { tenant_id: 'tenant-1', name: 'Cable Works' },
    },
  });
}

describe('team roster mutations', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCallerId = 'user-1';
    mockActiveTenantId = 'tenant-1';
    currentUserService();
  });

  describe('changing a member role', () => {
    it('invalidates the roster and the joined-workspace list', async () => {
      mockUpdateTenantUserRole.mockResolvedValue({
        data: { code: 0 },
      });
      const queryClient = makeClient();
      seedActiveWorkspaceCaches(queryClient);
      const invalidate = jest.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useUpdateTenantUserRole(), {
        wrapper: makeWrapper(queryClient),
      });
      await result.current.updateTenantUserRole({
        userId: 'user-2',
        role: 'admin',
      });

      expect(mockUpdateTenantUserRole).toHaveBeenCalledWith({
        tenantId: 'tenant-1',
        userId: 'user-2',
        role: 'admin',
      });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['listTenantUser'] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['listTenant'] });
      expect(isInvalidated(queryClient, ROSTER_KEY)).toBe(true);
    });

    it('leaves the roster valid when the server refuses the change', async () => {
      mockUpdateTenantUserRole.mockResolvedValue({ data: { code: 108 } });
      const queryClient = makeClient();
      seedActiveWorkspaceCaches(queryClient);

      const { result } = renderHook(() => useUpdateTenantUserRole(), {
        wrapper: makeWrapper(queryClient),
      });
      await result.current.updateTenantUserRole({
        userId: 'user-2',
        role: 'admin',
      });

      expect(isInvalidated(queryClient, ROSTER_KEY)).toBe(false);
    });
  });

  describe('removing a member', () => {
    it('invalidates the roster and the joined-workspace list', async () => {
      mockDeleteTenantUser.mockResolvedValue({ data: { code: 0, data: true } });
      const queryClient = makeClient();
      seedActiveWorkspaceCaches(queryClient);
      const invalidate = jest.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useDeleteTenantUser(), {
        wrapper: makeWrapper(queryClient),
      });
      await result.current.deleteTenantUser({ userId: 'user-2' });

      expect(mockDeleteTenantUser).toHaveBeenCalledWith({
        tenantId: 'tenant-1',
        userId: 'user-2',
      });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['listTenantUser'] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['listTenant'] });
      expect(isInvalidated(queryClient, ROSTER_KEY)).toBe(true);
    });

    it('keeps the caller inside the workspace when someone else was removed', async () => {
      mockDeleteTenantUser.mockResolvedValue({ data: { code: 0, data: true } });
      const queryClient = makeClient();
      seedActiveWorkspaceCaches(queryClient);

      const { result } = renderHook(() => useDeleteTenantUser(), {
        wrapper: makeWrapper(queryClient),
      });
      await result.current.deleteTenantUser({ userId: 'user-2' });

      // Only the caller's own removal is a departure; the workspace record the
      // page reads keeps resolving to the workspace they are still in.
      expect(mockSetActiveTenantId).not.toHaveBeenCalledWith(null);
    });

    it('gives up the stored workspace when the caller leaves it', async () => {
      mockDeleteTenantUser.mockResolvedValue({ data: { code: 0, data: true } });
      const queryClient = makeClient();
      seedActiveWorkspaceCaches(queryClient);
      const invalidate = jest.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useDeleteTenantUser(), {
        wrapper: makeWrapper(queryClient),
      });
      await result.current.deleteTenantUser({
        userId: mockCallerId,
        tenantId: 'tenant-1',
      });

      // The server drops the membership with the selection; the header value
      // must not keep naming a workspace the caller is no longer in.
      expect(mockSetActiveTenantId).toHaveBeenCalledWith(null);
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['tenantInfo'] });
    });
  });

  describe('inviting a member', () => {
    it('forwards the department and title chosen in the dialog', async () => {
      mockAddTenantUser.mockResolvedValue({ data: { code: 0 } });
      const queryClient = makeClient();
      seedActiveWorkspaceCaches(queryClient);

      const { result } = renderHook(() => useAddTenantUser(), {
        wrapper: makeWrapper(queryClient),
      });
      await result.current.addTenantUser({
        email: 'someone@example.com',
        role: 'admin',
        departmentId: 'department-1',
        title: 'Sales manager',
      });

      expect(mockAddTenantUser).toHaveBeenCalledWith(
        'tenant-1',
        'someone@example.com',
        'admin',
        { departmentId: 'department-1', title: 'Sales manager' },
      );
      expect(isInvalidated(queryClient, ROSTER_KEY)).toBe(true);
    });
  });

  describe('accepting an invitation', () => {
    it('persists the switch and re-keys the roster onto the new workspace', async () => {
      mockAgreeTenant.mockResolvedValue({ data: { code: 0, data: true } });
      const queryClient = makeClient();
      seedActiveWorkspaceCaches(queryClient);
      const invalidate = jest.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useAgreeTenant(), {
        wrapper: makeWrapper(queryClient),
      });
      await result.current.agreeTenant('tenant-9');

      expect(mockAgreeTenant).toHaveBeenCalledWith('tenant-9');
      // Accepting also makes that workspace active server-side.
      expect(mockSetActiveTenantId).toHaveBeenCalledWith('tenant-9');
      // The tenant record is what the roster is keyed off, so refetching it is
      // what moves the roster onto the new workspace.
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['tenantInfo'] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['listTenantUser'] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['listTenant'] });
      expect(isInvalidated(queryClient, ROSTER_KEY)).toBe(true);
    });

    it('leaves the stored workspace alone when there was no invitation', async () => {
      mockAgreeTenant.mockResolvedValue({ data: { code: 108 } });
      const queryClient = makeClient();
      seedActiveWorkspaceCaches(queryClient);

      const { result } = renderHook(() => useAgreeTenant(), {
        wrapper: makeWrapper(queryClient),
      });
      await result.current.agreeTenant('tenant-9');

      expect(mockSetActiveTenantId).not.toHaveBeenCalled();
      expect(isInvalidated(queryClient, ROSTER_KEY)).toBe(false);
    });
  });

  describe('reading the roster', () => {
    it('keys it on the active workspace', async () => {
      const listTenantUser = jest.requireMock('@/services/user-service')
        .listTenantUser as jest.Mock;
      listTenantUser.mockResolvedValue({ data: { code: 0, data: [] } });
      const queryClient = makeClient();

      const { result } = renderHook(() => useListTenantUser(), {
        wrapper: makeWrapper(queryClient),
      });

      await waitFor(() =>
        expect(listTenantUser).toHaveBeenCalledWith('tenant-1'),
      );
      expect(queryClient.getQueryData(ROSTER_KEY)).toEqual([]);
      expect(result.current.data).toEqual([]);
    });
  });
});
