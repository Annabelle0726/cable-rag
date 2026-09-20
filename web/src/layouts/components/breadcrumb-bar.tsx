import { cn } from '@/lib/utils';
import { Routes } from '@/routes';
import { Fragment, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router';
import {
  BreadcrumbCrumb,
  useBreadcrumbEntityTrail,
} from './breadcrumb-context';

/**
 * A resolved level. Key levels are resolved here from a bundle key; the entity
 * levels published by the page arrive already translated.
 */
type Level =
  | { kind: 'key'; labelKey: string; to?: string }
  | { kind: 'text'; label: string; to?: string };

/** Matches on path-segment boundaries, so `/chats` never matches `/chat`. */
const isUnder = (pathname: string, root: string) =>
  pathname === root || pathname.startsWith(`${root}/`);

const Key = (labelKey: string, to?: string): Level => ({
  kind: 'key',
  labelKey,
  to,
});

const Text = (label: string, to?: string): Level => ({
  kind: 'text',
  label,
  to,
});

/** The knowledge-base sub-features, in the sidebar's own order. */
const DatasetSectionLabels: Record<string, string> = {
  [Routes.Files]: 'knowledgeDetails.subbarFiles',
  [Routes.DatasetTesting]: 'knowledgeDetails.testing',
  [Routes.DataSetOverview]: 'knowledgeDetails.overview',
  [Routes.DataSetSetting]: 'knowledgeDetails.configuration',
  [Routes.Compilation]: 'breadcrumb.artifact',
  [Routes.KnowledgeGraph]: 'knowledgeDetails.knowledgeGraph',
};

const MemorySectionLabels: Record<string, string> = {
  [Routes.MemoryMessage]: 'breadcrumb.messages',
  [Routes.MemorySetting]: 'breadcrumb.setting',
};

type Trail = {
  /** Levels derived from the path: the module, which is always a link. */
  module: Level[];
  /** The sub-page the path names, if any. Always the last level. */
  leaf?: Level;
};

/**
 * Resolve the path into the levels the URL alone can prove.
 *
 * Order matters: `/files/skills` is a route of its own and has to be tested before
 * the `/files` module it would otherwise match.
 */
const resolvePath = (pathname: string): Trail => {
  const segments = pathname.split('/').filter(Boolean);
  // The route constants carry a leading slash, so the segment has to be rebuilt
  // into the same shape before it can index the section maps below.
  const section = segments[1] ? `/${segments[1]}` : '';

  if (pathname === Routes.Root) {
    return { module: [Key('header.home')] };
  }

  if (isUnder(pathname, Routes.Skills)) {
    return {
      module: [Key('header.fileManager', Routes.Files), Key('header.skills')],
    };
  }

  if (isUnder(pathname, Routes.Files)) {
    return { module: [Key('header.fileManager')] };
  }

  if (
    isUnder(pathname, Routes.DatasetBase) ||
    isUnder(pathname, Routes.Datasets)
  ) {
    // 知识库 points at the global list, never at `/dataset`: that path is the
    // shell that renders a knowledge base's sidebar, so linking to it with no
    // knowledge base selected is what left a blank page beside a dead sidebar.
    const module = [Key('breadcrumb.datasetModule', Routes.Datasets)];
    const labelKey = DatasetSectionLabels[section];

    if (labelKey) {
      return { module, leaf: Key(labelKey) };
    }

    // `/dataset/:id` names a knowledge base whose path carries no sub-feature, so
    // its leaf is the knowledge base's own default view.
    return isUnder(pathname, Routes.DatasetBase)
      ? { module, leaf: Key('knowledgeDetails.subbarFiles') }
      : { module };
  }

  if (isUnder(pathname, Routes.Chats) || isUnder(pathname, Routes.Chat)) {
    return { module: [Key('header.chat', Routes.Chats)] };
  }

  if (isUnder(pathname, Routes.Agents) || isUnder(pathname, Routes.Agent)) {
    return { module: [Key('header.flow', Routes.Agents)] };
  }

  if (isUnder(pathname, Routes.Searches) || isUnder(pathname, Routes.Search)) {
    return { module: [Key('header.search', Routes.Searches)] };
  }

  if (isUnder(pathname, Routes.Memories) || isUnder(pathname, Routes.Memory)) {
    const labelKey = MemorySectionLabels[section];

    return {
      module: [Key('header.memories', Routes.Memories)],
      leaf: labelKey ? Key(labelKey) : undefined,
    };
  }

  if (isUnder(pathname, Routes.UserSetting)) {
    // The module level stays a link even though the page below publishes a second
    // level: `/user-setting` redirects to its default tab, so stepping up from
    // 团队 lands on the settings landing page instead of on nothing.
    return { module: [Key('header.setting', Routes.UserSetting)] };
  }

  return { module: [] };
};

function useTrail(): Level[] {
  const { pathname } = useLocation();
  const entityTrail = useBreadcrumbEntityTrail();

  return useMemo(() => {
    const { module, leaf } = resolvePath(pathname);
    const entity: Level[] = entityTrail.map((crumb: BreadcrumbCrumb) =>
      Text(crumb.label, crumb.to),
    );

    // Module, then the entity the page is showing, then the page's own level:
    // 知识库 > 国家及行业规范 > 文件列表.
    return [...module, ...entity, ...(leaf ? [leaf] : [])];
  }, [entityTrail, pathname]);
}

/**
 * Breadcrumb rail under the header. A plain white strip closed by a 1px hairline,
 * 12px secondary ink: it says where in the console the operator is without
 * competing with the page title.
 *
 * Every level above the last is a link to its parent route; the last is the page
 * itself and is not clickable, so the rail can never offer a jump to a parent that
 * renders nothing. The trail starts at the current module, so a module page
 * carries a single level and a page inside one carries the module, the entity it
 * belongs to and the sub-page; only the home route reads as 首页.
 */
export function BreadcrumbBar({ className }: { className?: string }) {
  const { t } = useTranslation();
  const trail = useTrail();

  const labelOf = (level: Level) =>
    level.kind === 'key' ? t(level.labelKey) : level.label;

  // Nothing resolved (a route outside the console): 首页 keeps the rail from
  // collapsing into an empty strip.
  const levels = trail.length ? trail : [Key('header.home')];

  return (
    <nav
      aria-label="breadcrumb"
      className={cn(
        'page-gutter flex h-8 shrink-0 items-center border-b border-panel-border bg-bg-component text-xs text-content-secondary',
        className,
      )}
    >
      <ol className="flex min-w-0 items-center gap-2">
        {levels.map((level, index) => {
          const isCurrent = index === levels.length - 1;
          const label = labelOf(level);

          return (
            <Fragment key={`${level.kind}-${label}-${index}`}>
              {index > 0 && (
                <li aria-hidden className="shrink-0 text-text-disabled">
                  &gt;
                </li>
              )}
              <li className="flex min-w-0 items-center">
                {isCurrent || !level.to ? (
                  <span
                    aria-current={isCurrent ? 'page' : undefined}
                    className={cn(
                      'truncate',
                      isCurrent && 'font-medium text-text-primary',
                    )}
                  >
                    {label}
                  </span>
                ) : (
                  <Link
                    to={level.to}
                    title={label}
                    className="truncate transition-colors hover:text-cable-brand"
                  >
                    {label}
                  </Link>
                )}
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
