import { cn } from '@/lib/utils';
import { Fragment, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router';

/**
 * Path segment → crumb label. The first labelled segment is the module itself
 * (`/chats` reads as 聊天, not 首页 > 聊天) and the ones under it are the pages
 * beneath that module (`/files/skills` reads as 文件管理 > Skills).
 *
 * Segments with no label — route parameters, mostly — are dropped, so a trail
 * never leaks a raw uuid.
 */
const SegmentLabels: Record<string, string> = {
  datasets: 'breadcrumb.datasetModule',
  dataset: 'header.dataset',
  files: 'header.fileManager',
  skills: 'header.skills',
  chats: 'header.chat',
  chat: 'header.chat',
  searches: 'header.search',
  search: 'header.search',
  agents: 'header.flow',
  agent: 'header.flow',
  memories: 'header.memories',
  memory: 'header.memories',
  'user-setting': 'header.setting',
};

type Crumb = { labelKey: string; to: string };

function useCrumbs() {
  const { pathname } = useLocation();

  return useMemo(() => {
    const crumbs: Crumb[] = [];
    const segments = pathname.split('/').filter(Boolean);

    segments.forEach((segment, index) => {
      const labelKey = SegmentLabels[segment];
      if (!labelKey) {
        return;
      }
      // Two segments of the same module (`/dataset/files`) are one level, not two.
      if (crumbs.at(-1)?.labelKey === labelKey) {
        return;
      }
      crumbs.push({
        labelKey,
        to: `/${segments.slice(0, index + 1).join('/')}`,
      });
    });

    return crumbs;
  }, [pathname]);
}

/**
 * Breadcrumb rail under the header. A plain white strip closed by a 1px hairline,
 * 12px secondary ink: it says where in the console the operator is without
 * competing with the page title. The trail starts at the current module, so a
 * module page carries a single crumb and a page below it carries the module plus
 * the page; only the home route itself reads as 首页.
 */
export function BreadcrumbBar({ className }: { className?: string }) {
  const { t } = useTranslation();
  const crumbs = useCrumbs();

  return (
    <nav
      aria-label="breadcrumb"
      className={cn(
        'page-gutter flex h-8 shrink-0 items-center border-b border-panel-border bg-bg-component text-xs text-content-secondary',
        className,
      )}
    >
      <ol className="flex min-w-0 items-center gap-2">
        {crumbs.length === 0 ? (
          <li className="flex min-w-0 items-center">
            <span
              aria-current="page"
              className="truncate font-medium text-text-primary"
            >
              {t('header.home')}
            </span>
          </li>
        ) : (
          crumbs.map((crumb, index) => {
            const isLast = index === crumbs.length - 1;

            return (
              <Fragment key={crumb.to}>
                {index > 0 && (
                  <li aria-hidden className="shrink-0 text-text-disabled">
                    &gt;
                  </li>
                )}
                <li className="flex min-w-0 items-center">
                  {isLast ? (
                    <span
                      aria-current="page"
                      className="truncate font-medium text-text-primary"
                    >
                      {t(crumb.labelKey)}
                    </span>
                  ) : (
                    <Link
                      to={crumb.to}
                      className="truncate transition-colors hover:text-cable-brand"
                    >
                      {t(crumb.labelKey)}
                    </Link>
                  )}
                </li>
              </Fragment>
            );
          })
        )}
      </ol>
    </nav>
  );
}
