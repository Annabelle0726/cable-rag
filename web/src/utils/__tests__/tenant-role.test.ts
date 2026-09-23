import { TenantRole } from '@/pages/user-setting/constants';
import { canManageTenant } from '@/utils/tenant-role';

describe('canManageTenant', () => {
  it('admits a tenant owner, because OWNER implies ADMIN', () => {
    expect(canManageTenant(TenantRole.Owner)).toBe(true);
  });

  it('admits a tenant admin', () => {
    expect(canManageTenant(TenantRole.Admin)).toBe(true);
  });

  it('rejects a normal member', () => {
    expect(canManageTenant(TenantRole.Normal)).toBe(false);
  });

  it('rejects an invited-but-not-yet-accepted member', () => {
    expect(canManageTenant(TenantRole.Invite)).toBe(false);
  });

  it('rejects an unknown role rather than defaulting to allowed', () => {
    expect(canManageTenant('something-else')).toBe(false);
  });

  it('rejects a missing role, so servers predating this field do not grant access', () => {
    expect(canManageTenant(undefined)).toBe(false);
    expect(canManageTenant('')).toBe(false);
  });
});
