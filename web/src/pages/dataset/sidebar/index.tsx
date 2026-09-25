import { useCallback, useMemo } from 'react';
import { useLocalStorageState } from 'ahooks';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useTranslation } from 'react-i18next';

import {
  PanelLeftClose,
  PanelLeftOpen,
  LucideBookText,
  LucideFolderOpen,
  LucideLogs,
  LucideSettings,
  LucideTextSearch,
} from 'lucide-react';

import { DatasetIdentityMark } from '@/components/dataset-category';
import { Button } from '@/components/ui/button';
import { useSecondPathName } from '@/hooks/route-hook';
import { cn, formatBytes } from '@/lib/utils';
import { Routes } from '@/routes';
import { formatPureDate } from '@/utils/date';

import { IDataset } from '@/interfaces/database/dataset';
import { useParams } from 'react-router';

type PropType = {
  refreshCount?: number;
  dataset: IDataset;
};

export function SideBar({ dataset: data }: PropType) {
  const [collapsed, setCollapsed] = useLocalStorageState<boolean>(
    'dataset_sidebar_collapsed',
    { defaultValue: false },
  );
  const toggleCollapsed = useCallback(
    () => setCollapsed((value) => !value),
    [setCollapsed],
  );
  const pathName = useSecondPathName();
  const { id } = useParams();
  const { t } = useTranslation();

  const items = useMemo(() => {
    const list = [
      {
        icon: <LucideFolderOpen className="size-[1em]" />,
        label: t(`knowledgeDetails.subbarFiles`),
        key: Routes.Files,
      },
      {
        icon: <LucideTextSearch className="size-[1em]" />,
        label: t(`knowledgeDetails.testing`),
        key: Routes.DatasetTesting,
      },
      {
        icon: <LucideLogs className="size-[1em]" />,
        label: t(`knowledgeDetails.overview`),
        key: Routes.DataSetOverview,
      },
      {
        icon: <LucideSettings className="size-[1em]" />,
        label: t(`knowledgeDetails.configuration`),
        key: Routes.DataSetSetting,
      },
      {
        icon: <LucideBookText className="size-[1em]" />,
        label: 'Artifacts',
        key: Routes.Compilation,
      },
    ];

    return list;
  }, [t]);

  return (
    <aside
      className={cn(
        'flex shrink-0 flex-col relative min-h-0 transition-[width] duration-200 ease-in-out motion-reduce:transition-none',
        collapsed ? 'w-16' : 'w-64',
      )}
      data-collapsed={Boolean(collapsed)}
    >
      <div className="flex justify-end px-3 pb-3">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleCollapsed}
              aria-expanded={!collapsed}
              aria-label={t(
                collapsed
                  ? 'knowledgeDetails.expandSidebar'
                  : 'knowledgeDetails.collapseSidebar',
              )}
            >
              {collapsed ? (
                <PanelLeftOpen className="size-4" />
              ) : (
                <PanelLeftClose className="size-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {t(
              collapsed
                ? 'knowledgeDetails.expandSidebar'
                : 'knowledgeDetails.collapseSidebar',
            )}
          </TooltipContent>
        </Tooltip>
      </div>
      {!collapsed && (
        <header
          className="px-5 pb-4 grid grid-cols-[auto_1fr] grid-rows-[auto_auto] gap-x-3"
          style={{
            gridTemplateAreas: '"avatar title" "avatar stats"',
          }}
        >
          {/* The same mark the knowledge-base card shows: the owner's uploaded image
            when there is one, the class icon otherwise — never the first character
            of the name. */}
          <DatasetIdentityMark
            dataset={data}
            className="size-16"
            iconClassName="size-7"
            style={{ gridArea: 'avatar' }}
          />

          <h3
            className="text-lg font-semibold line-clamp-1 text-text-primary text-ellipsis overflow-hidden"
            style={{ gridArea: 'title' }}
          >
            {data.name}
          </h3>

          <div
            className="self-end text-text-secondary text-xs overflow-hidden"
            style={{ gridArea: 'stats' }}
          >
            <div className="flex justify-between">
              <span>
                {data.document_count} {t('knowledgeDetails.files')}
              </span>
              <span>{data.size ? formatBytes(data.size) : ''}</span>
            </div>

            <div className="mt-0.5">
              {t('knowledgeDetails.created')} {formatPureDate(data.create_time)}
            </div>
          </div>
        </header>
      )}

      <nav
        className={cn('pt-1 pb-5 overflow-y-auto', collapsed ? 'px-2' : 'px-5')}
      >
        <ul className="space-y-5">
          {items.map((item) => {
            const active = '/' + pathName === item.key;

            return (
              <li key={item.key}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      aria-label={item.label}
                      aria-current={active ? 'page' : undefined}
                      asLink
                      block
                      variant="ghost"
                      className={cn(
                        'justify-start gap-2.5 px-3 relative h-10 text-base',
                        collapsed && 'justify-center px-0',
                        active && 'bg-bg-card text-text-primary',
                      )}
                      to={`${Routes.DatasetBase}${item.key}/${id}`}
                    >
                      {item.icon}
                      {!collapsed && <span>{item.label}</span>}
                    </Button>
                  </TooltipTrigger>
                  {collapsed && (
                    <TooltipContent side="right">{item.label}</TooltipContent>
                  )}
                </Tooltip>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
