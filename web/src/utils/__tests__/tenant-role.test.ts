import { TenantRole } from '@/pages/user-setting/constants';
import { canManageTenant, getRoleDisplayConfig } from '@/utils/tenant-role';

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

describe('getRoleDisplayConfig', () => {
  it('labels each known role through a translation key, never a literal', () => {
    expect(getRoleDisplayConfig(TenantRole.Owner).labelKey).toBe(
      'setting.roleOwner',
    );
    expect(getRoleDisplayConfig(TenantRole.Admin).labelKey).toBe(
      'setting.roleAdmin',
    );
    expect(getRoleDisplayConfig(TenantRole.Normal).labelKey).toBe(
      'setting.roleMember',
    );
    expect(getRoleDisplayConfig(TenantRole.Invite).labelKey).toBe(
      'setting.roleInvite',
    );
  });

  it('distinguishes owner from admin visually', () => {
    expect(getRoleDisplayConfig(TenantRole.Owner).badgeClass).not.toBe(
      getRoleDisplayConfig(TenantRole.Admin).badgeClass,
    );
  });

  it('falls back to the neutral member presentation for an unknown role', () => {
    expect(getRoleDisplayConfig('something-else')).toEqual(
      getRoleDisplayConfig(TenantRole.Normal),
    );
  });

  it('falls back to the neutral member presentation when the role is absent', () => {
    expect(getRoleDisplayConfig(undefined)).toEqual(
      getRoleDisplayConfig(TenantRole.Normal),
    );
    expect(getRoleDisplayConfig('')).toEqual(
      getRoleDisplayConfig(TenantRole.Normal),
    );
  });

  it('uses only semantic colour tokens, never Tailwind default palette colours', () => {
    // web/CLAUDE.md forbids Tailwind's default palette in component classes.
    // This guards the mapping (and caught the pre-existing ColorMap in
    // setting-team/user-table.tsx) from drifting back to gray-*/amber-* etc.
    const defaultPalette =
      /\b(?:bg|text|border|hover:bg|hover:text)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/;

    for (const role of Object.values(TenantRole)) {
      expect(getRoleDisplayConfig(role).badgeClass).not.toMatch(defaultPalette);
    }
    expect(getRoleDisplayConfig(undefined).badgeClass).not.toMatch(
      defaultPalette,
    );
  });

  it('gives every role a non-empty badge class', () => {
    for (const role of [...Object.values(TenantRole), undefined, 'unknown']) {
      expect(getRoleDisplayConfig(role).badgeClass.trim()).not.toBe('');
    }
  });
});
