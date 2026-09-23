import { useTranslation } from 'react-i18next';

import { cn } from '@/lib/utils';
import { getRoleDisplayConfig } from '@/utils/tenant-role';

interface RoleTagProps {
  /** The caller's role, as returned by `GET /users/me`. */
  role?: string;
  className?: string;
}

/**
 * Read-only tag showing a tenant role.
 *
 * Styling comes from `getRoleDisplayConfig` so every role render in the app
 * shares one mapping. `rounded-[2px]` follows the industrial squared-corner
 * token (`--radius: 2px`) rather than the shared Badge's `rounded-full`.
 */
const RoleTag = ({ role, className }: RoleTagProps) => {
  const { t } = useTranslation();
  const { labelKey, badgeClass } = getRoleDisplayConfig(role);

  return (
    <span
      data-testid="role-tag"
      data-role={role ?? ''}
      className={cn(
        'inline-flex items-center rounded-[2px] border px-2 py-0.5 text-xs font-medium transition-colors',
        badgeClass,
        className,
      )}
    >
      {t(labelKey)}
    </span>
  );
};

export default RoleTag;
