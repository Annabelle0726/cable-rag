import { useId, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router';

import {
  LucideBot,
  LucideBrain,
  LucideDatabase,
  LucideFolderOpen,
  LucideHouse,
  LucideMenu,
  LucideMessagesSquare,
  LucideSearch,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { Routes } from '@/routes';
import { supportsCssAnchor } from '@/utils/css-support';
import { BrandMark } from './brand-mark';
import { DatasetNavMenu } from './dataset-nav-menu';

const PathMap = {
  [Routes.Datasets]: [Routes.Datasets, Routes.DatasetBase],
  [Routes.Chats]: [Routes.Chats, Routes.Chat],
  [Routes.Searches]: [Routes.Searches, Routes.Search],
  [Routes.Agents]: [Routes.Agents, Routes.AgentTemplates],
  [Routes.Memories]: [Routes.Memories, Routes.Memory, Routes.MemoryMessage],
  [Routes.Files]: [Routes.Files],
} as const;

// Match on path-segment boundaries, not a loose substring, so e.g.
// "/user-setting/chat-channel" does not match the "/chat" tab.
const matchesPath = (pathname: string, candidate: string) =>
  pathname === candidate || pathname.startsWith(`${candidate}/`);

// Every tab carries an icon: a bare text row reads as a list of links, while an
// icon + label pair reads as navigation and is recognisable at a glance. Lucide
// shapes are used (rather than bitmaps) so they inherit the token colours and
// stay crisp at any density.
const menuItems = [
  { path: Routes.Root, name: 'header.home', icon: LucideHouse },
  {
    path: Routes.Datasets,
    name: 'header.dataset',
    icon: LucideDatabase,
    'data-testid': 'nav-dataset',
  },
  {
    path: Routes.Chats,
    name: 'header.chat',
    icon: LucideMessagesSquare,
    'data-testid': 'nav-chat',
  },
  {
    path: Routes.Searches,
    name: 'header.search',
    icon: LucideSearch,
    'data-testid': 'nav-search',
  },
  {
    path: Routes.Agents,
    name: 'header.flow',
    icon: LucideBot,
    'data-testid': 'nav-agent',
  },
  {
    path: Routes.Memories,
    name: 'header.memories',
    icon: LucideBrain,
  },
  {
    path: Routes.Files,
    name: 'header.fileManager',
    icon: LucideFolderOpen,
  },
];

function useActivePath() {
  const { pathname } = useLocation();

  return useMemo(() => {
    return (
      Object.keys(PathMap).find((x: string) =>
        PathMap[x as keyof typeof PathMap].some((y: string) =>
          matchesPath(pathname, y),
        ),
      ) || pathname
    );
  }, [pathname]);
}

/**
 * One shape for both desktop variants: icon and label on one line, vertically
 * centred, with an 8px gap. The row stays 32px tall, so the bar's own padding is
 * what sets the header height. Shared with the knowledge-base menu, whose
 * trigger is the same navigation link.
 *
 * Interaction ink is the brand accent throughout — hover, open and keyboard
 * focus all colour the label the same way. The near-black hover ink it used to
 * switch to read as an accident in the light theme, and keyboard focus now
 * draws its own 2px accent ring instead of relying on the browser's outline.
 */
const desktopNavLinkClass = (isActive: boolean) =>
  cn(
    'inline-flex h-8 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 text-sm',
    'transition-colors duration-200 ease-in-out',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cable-nav-indicator',
    isActive
      ? 'font-semibold text-cable-nav-active-text'
      : 'text-cable-nav hover:text-cable-nav-active-text focus-visible:text-cable-nav-active-text',
  );

/** Variant for browsers without CSS anchor positioning: the item highlights itself. */
const fallbackNavLinkClass = (isActive: boolean) =>
  cn(
    'inline-flex h-8 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 text-sm',
    'transition-colors duration-200 ease-in-out',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cable-nav-indicator',
    isActive
      ? 'border-b-2 border-b-cable-nav-indicator bg-cable-nav-active-bg font-semibold text-cable-nav-active-text shadow-accent-glow'
      : 'text-cable-nav hover:bg-cable-nav-active-bg hover:text-cable-nav-active-text focus-visible:text-cable-nav-active-text',
  );

const DesktopNavbarWithAnchor = () => {
  const { t } = useTranslation();
  const activePath = useActivePath();
  const navbarAnchorNamePrefix = useId().replace(/:/g, '');

  const activePathAnchorName = `--${navbarAnchorNamePrefix}${activePath === Routes.Root ? '-root' : activePath.replace('/', '-')}`;

  const hasAnyActive = useMemo(
    () => menuItems.some(({ path }) => path === activePath),
    [activePath],
  );

  return (
    <nav>
      {/* The nav is a pill inside the bar: the padding on all four sides keeps
          the items from pressing against its own edge, and the ceramic shell
          supplies the surface, the hairline and the elevation in both themes. */}
      <ul className="ceramic-pill relative flex items-center gap-1 rounded-xl p-1.5">
        {menuItems.map(({ path, name, icon: Icon, ...props }) => {
          const isActive = path === activePath;
          const anchorName = `--${navbarAnchorNamePrefix}${path === Routes.Root ? '-root' : path.replace('/', '-')}`;

          return (
            <li key={path} className="relative" style={{ anchorName }}>
              {path === Routes.Datasets ? (
                // The knowledge base carries the plant's own two-level menu:
                // classification, then that class's knowledge bases.
                <DatasetNavMenu
                  to={path}
                  label={t(name)}
                  icon={Icon}
                  isActive={isActive}
                  testId={props['data-testid']}
                  className={desktopNavLinkClass(isActive)}
                />
              ) : (
                <Link
                  {...props}
                  to={path}
                  className={desktopNavLinkClass(isActive)}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon className="size-4 shrink-0 stroke-[1.75]" />
                  <span>{t(name)}</span>
                </Link>
              )}
            </li>
          );
        })}

        {/* Sliding highlight: a soft brand-tinted capsule closing with a 2px
            indicator line, positioned over the active item by CSS anchor
            positioning. */}
        <li
          className={cn(
            // The capsule re-anchors to the active item, so only its opacity
            // animates; the single-colour accent glow marks the current tab.
            'absolute -z-[1] rounded-lg border-b-2 border-b-cable-nav-indicator bg-cable-nav-active-bg opacity-0 shadow-accent-glow',
            'transition-opacity duration-200 ease-in-out',
            hasAnyActive && 'opacity-100',
          )}
          role="presentation"
          style={{
            top: 'anchor(top)',
            left: 'anchor(left)',
            width: 'anchor-size(width)',
            height: 'anchor-size(height)',
            positionAnchor: activePathAnchorName,
          }}
        />
      </ul>
    </nav>
  );
};

const DesktopNavbarFallback = () => {
  const { t } = useTranslation();
  const activePath = useActivePath();

  return (
    <nav>
      <ul className="ceramic-pill flex items-center gap-1 rounded-xl p-1.5">
        {menuItems.map(({ path, name, icon: Icon, ...props }) => {
          const isActive = path === activePath;

          return (
            <li key={path}>
              {path === Routes.Datasets ? (
                <DatasetNavMenu
                  to={path}
                  label={t(name)}
                  icon={Icon}
                  isActive={isActive}
                  testId={props['data-testid']}
                  className={fallbackNavLinkClass(isActive)}
                />
              ) : (
                <Link
                  {...props}
                  to={path}
                  className={fallbackNavLinkClass(isActive)}
                  aria-label={t(name)}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon className="size-4 shrink-0 stroke-[1.75]" />
                  <span>{t(name)}</span>
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
};

export function DesktopNavbar() {
  return supportsCssAnchor ? (
    <DesktopNavbarWithAnchor />
  ) : (
    <DesktopNavbarFallback />
  );
}

function MobileNavItem({
  label,
  icon: Icon,
  isActive,
  onClick,
  ...linkProps
}: {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  isActive?: boolean;
  onClick?: () => void;
  to: string;
  'data-testid'?: string;
}) {
  return (
    <Link
      {...linkProps}
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-3.5 px-4 py-3.5 text-base',
        'text-cable-nav transition-colors hover:bg-cable-nav-active-bg hover:text-cable-nav-active-text',
        'focus-visible:outline-none focus-visible:bg-cable-nav-active-bg focus-visible:text-cable-nav-active-text',
        isActive &&
          'border-l-2 border-cable-nav-indicator bg-cable-nav-active-bg font-semibold text-cable-nav-active-text',
      )}
      aria-current={isActive ? 'page' : undefined}
    >
      <Icon className="size-5 shrink-0 stroke-[1.75]" />
      <span className="truncate">{label}</span>
    </Link>
  );
}

type MobileNavbarProps = {
  renderFooter?: (close: () => void) => React.ReactNode;
};

export function MobileNavbar({ renderFooter }: MobileNavbarProps) {
  const { t } = useTranslation();
  const activePath = useActivePath();
  const [open, setOpen] = useState(false);

  const close = () => setOpen(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="size-10 shrink-0"
          aria-label="Menu"
        >
          <LucideMenu className="size-6 stroke-[1.75]" />
        </Button>
      </SheetTrigger>

      <SheetContent
        side="left"
        closeIcon={false}
        className="flex w-[min(85vw,18rem)] flex-col gap-0 p-0 sm:w-72"
      >
        <div className="flex shrink-0 items-center justify-center gap-3 py-5">
          <BrandMark label={t('header.brandShort')} />
          <span className="text-base font-semibold tracking-tight text-cable-brand">
            {t('header.brandShort')}
          </span>
        </div>

        <nav className="min-h-0 flex-1 overflow-y-auto py-3">
          <ul className="space-y-1">
            {menuItems.map(({ path, name, icon, ...props }) => (
              <li key={path}>
                <MobileNavItem
                  {...props}
                  to={path}
                  label={t(name)}
                  icon={icon}
                  isActive={path === activePath}
                  onClick={close}
                />
              </li>
            ))}
          </ul>
        </nav>

        {renderFooter?.(close)}
      </SheetContent>
    </Sheet>
  );
}

const GlobalNavbar = DesktopNavbar;

export default GlobalNavbar;
