import { renderHook } from '@testing-library/react';
import { useCanManageDataset } from '../use-can-manage-dataset';

let mockUser = { id: 'reader' };
let mockTenant = { tenant_id: 'tenant-1', role: 'normal' };
jest.mock('../use-user-setting-request', () => ({
  useFetchUserInfo: () => ({ data: mockUser }),
  useFetchTenantInfo: () => ({ data: mockTenant }),
}));
const dataset = { created_by: 'creator', tenant_id: 'tenant-1' };
it.each([
  ['reader', 'normal', 'tenant-1', false],
  ['creator', 'normal', 'tenant-1', true],
  ['reader', 'admin', 'tenant-1', true],
  ['reader', 'owner', 'tenant-1', true],
  ['reader', 'admin', 'other-tenant', false],
  ['', 'owner', 'tenant-1', false],
])('checks %s / %s in %s', (id, role, tenantId, expected) => {
  mockUser = { id };
  mockTenant = { tenant_id: tenantId, role };
  expect(renderHook(() => useCanManageDataset(dataset)).result.current).toBe(
    expected,
  );
});
