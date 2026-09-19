import { RAGFlowAvatar } from '@/components/ragflow-avatar';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useChangeLanguage } from '@/hooks/logic-hooks';
import {
  useFetchUserInfo,
  useListTenant,
} from '@/hooks/use-user-setting-request';
import { cn } from '@/lib/utils';
import { TenantRole } from '@/pages/user-setting/constants';
import { Routes } from '@/routes';
import { LucideLanguages } from 'lucide-react';
import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router';
import { BellButton } from './bell-button';
import { BrandMark } from './brand-mark';
import { DesktopNavbar, MobileNavbar } from './global-navbar';
import { MobileMenuFooter } from './mobile-menu-footer';
import ThemeButton from './theme-button';
import { useHeaderNavLayout } from './use-header-nav-layout';

import { supportedLanguages } from '@/locales/config';

/**
 * One shared shape for every header control, so the right-hand cluster reads as a
 * single row of micro-components instead of a row of mixed buttons. The ink is
 * spelled out in utilities rather than in a components-layer class: the `Button`
 * primitive already ships `text-text-secondary`, and a utility emitted later in
 * the stylesheet is the only thing that outranks it.
 */
const headerControlClass =
  'size-8 shrink-0 p-0 text-white/85 hover:bg-gov-header-hover hover:text-white focus-visible:bg-gov-header-hover focus-visible:text-white';

/**
 * Local override of the shared `--cable-nav-*` tokens.
 *
 * Those tokens are also read by white-background surfaces — the segmented tab
 * switch, the pagination, the file cells — where the ink has to stay mid-grey
 * (`#606266`) with a 国网绿 selection. On the solid green bar the same three
 * tokens must resolve to white ink instead, so they are re-declared here rather
 * than redefined globally: everything inside the header inherits the white ramp,
 * and every surface outside it keeps the page ramp untouched.
 */
const headerNavTokens =
  '[--cable-nav-text:rgba(255,255,255,0.85)] [--cable-nav-text-hover:#ffffff] [--cable-nav-active-text:#ffffff] [--cable-nav-active-bg:#005c3f] [--cable-nav-indicator:#ffffff]';

export function Header({
  className,
  ...props
}: React.HTMLAttributes<HTMLElement>) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const changeLanguage = useChangeLanguage();

  const {
    data: { language = 'en', avatar, nickname, email },
  } = useFetchUserInfo();

  const { data: tenantData } = useListTenant();
  const hasNotification = useMemo(
    () => tenantData?.some((x) => x.role === TenantRole.Invite),
    [tenantData],
  );

  const currentLanguage = supportedLanguages.find((x) => x.code === language);

  const {
    headerRef,
    logoRef,
    expandedRightMeasureRef,
    navMeasureRef,
    isCompact,
  } = useHeaderNavLayout(`${hasNotification}-${language}`);

  return (
    <>
      <header
        ref={headerRef}
        key="app-navbar"
        className={cn(
          // The bar is a fixed 48px rail. `page-gutter` only aligns these controls
          // with the page columns below, and `items-center` keeps every control on
          // the bar's centre line. The solid green surface belongs to the
          // full-width bar in the layout, not to this row.
          'page-gutter flex h-12 min-w-0 items-center gap-2 sm:gap-4',
          headerNavTokens,
          className,
        )}
        {...props}
      >
        <div className="inline-flex shrink-0 items-center gap-2">
          {isCompact && (
            <MobileNavbar
              renderFooter={(close) => <MobileMenuFooter onClose={close} />}
            />
          )}
          <div ref={logoRef} className="inline-flex shrink-0 items-center">
            {/* Mark and wordmark share one capsule: the mark has no surface of
                its own, so nothing reads as a box inside a box. */}
            <Link
              to={Routes.Root}
              aria-current={pathname === Routes.Root ? 'page' : undefined}
              className="brand-entry flex shrink-0 items-center gap-2 px-2 py-1"
              data-testid="brand-entry"
            >
              <BrandMark label={t('header.brandShort')} />
              <span className="hidden text-[15px] font-semibold tracking-tight text-gov-header-fg md:inline">
                {t('header.brandShort')}
              </span>
            </Link>
          </div>
        </div>

        {!isCompact && (
          <div className="flex min-w-0 flex-1 items-center overflow-x-clip">
            <DesktopNavbar />
          </div>
        )}

        {isCompact && <div className="flex-1" aria-hidden />}

        <div
          className={cn(
            'flex shrink-0 items-center justify-end',
            isCompact ? 'gap-0.5' : 'gap-1',
          )}
          data-testid="auth-status"
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className={headerControlClass}
                aria-label={currentLanguage?.displayName}
                title={currentLanguage?.displayName}
              >
                <LucideLanguages className="size-[1.05rem]" />
              </Button>
            </DropdownMenuTrigger>

            <DropdownMenuContent align="end">
              {supportedLanguages.map((x) => (
                <DropdownMenuItem
                  key={x.code}
                  onClick={() => changeLanguage(x.code)}
                >
                  {x.displayName}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {!isCompact && hasNotification && (
            <BellButton className={headerControlClass} />
          )}

          {/* Dark/light switch. The bar keeps its green in both modes, so the
              control only swaps its icon. */}
          <ThemeButton className={headerControlClass} />

          <Link
            to={Routes.UserSetting}
            className={cn(
              'relative flex size-8 shrink-0 items-center justify-center',
              'ring-1 ring-white/40 transition-[box-shadow] hover:ring-white',
              !isCompact && 'ms-2',
            )}
            data-testid="settings-entrypoint"
          >
            <RAGFlowAvatar
              name={nickname}
              email={email}
              avatar={avatar}
              isPerson
              className="size-8"
            />
          </Link>
        </div>
      </header>

      <div
        className="pointer-events-none invisible fixed -left-[9999px] top-0"
        aria-hidden
      >
        <div ref={navMeasureRef}>
          <DesktopNavbar />
        </div>
        {/* Mirrors the expanded right-hand cluster so the compact/nav-overflow
            measurement matches what actually renders. Keep the two in sync. */}
        <div
          ref={expandedRightMeasureRef}
          className="inline-flex shrink-0 items-center justify-end gap-1"
        >
          <Button variant="ghost" className={headerControlClass}>
            <LucideLanguages className="size-[1.05rem]" />
          </Button>
          <ThemeButton className={headerControlClass} />
          {hasNotification && <BellButton className={headerControlClass} />}
          <div className="relative ms-2 flex size-8 shrink-0 items-center justify-center">
            <RAGFlowAvatar
              name={nickname}
              email={email}
              avatar={avatar}
              isPerson
              className="size-8"
            />
          </div>
        </div>
      </div>
    </>
  );
}
