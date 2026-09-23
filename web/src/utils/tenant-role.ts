import { TenantRole } from '@/pages/user-setting/constants';

/**
 * Whether a role may administer its tenant.
 *
 * Mirrors the server-side hierarchy OWNER > ADMIN > NORMAL, where OWNER implies
 * ADMIN, so a tenant owner needs no separate grant. The server decides this
 * authoritatively (`UserTenantService.can_manage_tenant`); this helper only
 * drives UI affordances and must never be treated as the guard.
 */
export const canManageTenant = (role?: string): boolean =>
  role === TenantRole.Owner || role === TenantRole.Admin;
