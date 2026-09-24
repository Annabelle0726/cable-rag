import { TenantRole } from '@/pages/user-setting/constants';
import {
  canManageTenant,
  canRenderTenantControls,
  getRoleDisplayConfig,
  isAssignableTenantRole,
  isTenantMemberReadOnly,
} from '@/utils/tenant-role';

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

describe('isTenantMemberReadOnly', () => {
  it('is read-only for a member and for a merely invited user', () => {
    expect(isTenantMemberReadOnly(TenantRole.Normal)).toBe(true);
    expect(isTenantMemberReadOnly(TenantRole.Invite)).toBe(true);
  });

  it('is editable for an owner and for an admin', () => {
    expect(isTenantMemberReadOnly(TenantRole.Owner)).toBe(false);
    expect(isTenantMemberReadOnly(TenantRole.Admin)).toBe(false);
  });

  it('stays editable when the role is unknown, so an owner is never locked out', () => {
    // A server predating the role field reports nothing; presuming "member"
    // would hide every control from the very people allowed to use them.
    expect(isTenantMemberReadOnly(undefined)).toBe(false);
    expect(isTenantMemberReadOnly('')).toBe(false);
  });

  it('is read-only for an unrecognised role string', () => {
    expect(isTenantMemberReadOnly('something-else')).toBe(true);
  });
});

describe('isAssignableTenantRole', () => {
  it('admits the two roles the role endpoint can assign', () => {
    expect(isAssignableTenantRole(TenantRole.Admin)).toBe(true);
    expect(isAssignableTenantRole(TenantRole.Normal)).toBe(true);
  });

  it('rejects the owner, whose role is never assignable', () => {
    expect(isAssignableTenantRole(TenantRole.Owner)).toBe(false);
  });

  it('rejects a merely invited role, which the picker has no entry for', () => {
    // A select bound to `invite` would render blank instead of showing it.
    expect(isAssignableTenantRole(TenantRole.Invite)).toBe(false);
    expect(isAssignableTenantRole(undefined)).toBe(false);
    expect(isAssignableTenantRole('something-else')).toBe(false);
  });
});

describe('canRenderTenantControls', () => {
  it('renders the controls for an owner and for an admin', () => {
    expect(canRenderTenantControls(TenantRole.Owner)).toBe(true);
    expect(canRenderTenantControls(TenantRole.Admin)).toBe(true);
  });

  it('withholds them from a member and from a merely invited user', () => {
    expect(canRenderTenantControls(TenantRole.Normal)).toBe(false);
    expect(canRenderTenantControls(TenantRole.Invite)).toBe(false);
  });

  it('withholds them while the role is still unknown', () => {
    // `GET /users/me` starts empty, and `isTenantMemberReadOnly(undefined)` is
    // deliberately false so an unreported role cannot lock an owner out. As a
    // render gate that would flash the invite button and the roster controls at a
    // NORMAL member until the request lands, so a control waits for the role.
    expect(canRenderTenantControls(undefined)).toBe(false);
    expect(canRenderTenantControls('')).toBe(false);
  });

  it('withholds them for an unrecognised role', () => {
    expect(canRenderTenantControls('something-else')).toBe(false);
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
