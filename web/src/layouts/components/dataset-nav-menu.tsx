/*
 *  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
 *  Modifications Copyright 2026 线缆工业智搜平台. All Rights Reserved.
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

import { DatasetCategoryIcon } from '@/components/dataset-category';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Spin } from '@/components/ui/spin';
import {
  DatasetCategory,
  DatasetCategoryDefinitions,
  DatasetCategoryNavOrder,
  datasetsInNavCategory,
  groupDatasetsByCategory,
  resolveDatasetCategory,
} from '@/constants/dataset-category';
import { useNavigatePage } from '@/hooks/logic-hooks/navigate-hooks';
import { useFetchKnowledgeList } from '@/hooks/use-knowledge-request';
import { cn } from '@/lib/utils';
import { IDataset } from '@/interfaces/database/dataset';
import { Routes } from '@/routes';
import { LucideIcon, LucidePlus } from 'lucide-react';
import { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router';

const CloseDelayMs = 160;
const MenuPageSize = 100;
const NavbarEdgeOffset = 7;

type DatasetNavMenuProps = {
  to: string;
  label: string;
  icon: LucideIcon;
  isActive: boolean;
  className?: string;
  testId?: string;
};

export function DatasetNavMenu({
  to,
  label,
  icon: Icon,
  isActive,
  className,
  testId,
}: DatasetNavMenuProps) {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<number>();

  const cancelClose = useCallback(() => {
    if (closeTimer.current !== undefined) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = undefined;
    }
  }, []);

  const scheduleClose = useCallback(() => {
    cancelClose();
    closeTimer.current = window.setTimeout(() => setOpen(false), CloseDelayMs);
  }, [cancelClose]);

  const handleOpen = useCallback(() => {
    cancelClose();
    setOpen(true);
  }, [cancelClose]);

  const handlePreventAutoFocus = useCallback((event: Event) => {
    event.preventDefault();
  }, []);

  useEffect(() => cancelClose, [cancelClose]);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Link
          to={to}
          data-testid={testId}
          aria-current={isActive ? 'page' : undefined}
          aria-haspopup="true"
          aria-expanded={open}
          className={cn(
            className,
            'relative duration-150 data-[state=open]:bg-gov-header-hover data-[state=open]:text-gov-header-fg',
          )}
          onMouseEnter={handleOpen}
          onMouseLeave={scheduleClose}
          onFocus={handleOpen}
          onClick={scheduleClose}
        >
          <Icon className="size-4 shrink-0 stroke-[1.75]" />
          <span>{label}</span>

          {open ? (
            <span
              aria-hidden
              data-testid="nav-dataset-menu-bridge"
              className="absolute inset-x-0 top-full z-10 bg-gov-header-hover"
              style={{ height: NavbarEdgeOffset }}
            />
          ) : null}
        </Link>
      </PopoverTrigger>

      <PopoverContent
        align="start"
        sideOffset={NavbarEdgeOffset}
        onMouseEnter={cancelClose}
        onMouseLeave={scheduleClose}
        onOpenAutoFocus={handlePreventAutoFocus}
        /* 工业级面板：白底 + 1px 实线边框，无模糊、无投影。 */
        className={cn(
          'z-50 w-[min(92vw,28rem)] overflow-hidden outline-none',
          'border border-panel-border bg-bg-component p-0',
          'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        )}
        data-testid="nav-dataset-menu"
      >
        <DatasetNavMenuPanel onNavigate={scheduleClose} />
      </PopoverContent>
    </Popover>
  );
}

function DatasetNavMenuPanel({ onNavigate }: { onNavigate: () => void }) {
  const { t } = useTranslation();
  const { navigateToDatasetList } = useNavigatePage();
  const { list, loading } = useFetchKnowledgeList(false, '', MenuPageSize);
  const [activeCategory, setActiveCategory] = useState<DatasetCategory>(
    DatasetCategory.Bom,
  );

  const groups = useMemo(() => groupDatasetsByCategory(list), [list]);
  const visibleDatasets = datasetsInNavCategory(groups, activeCategory);

  return (
    <div className="flex min-h-[14rem] divide-x divide-cable-hairline">
      {/* 第一级：左侧分类列 - 浅灰底，与外框以 1px 分隔线相接 */}
      <ul className="w-[11.5rem] shrink-0 space-y-0.5 bg-bg-title p-2" role="list">
        {DatasetCategoryNavOrder.map((category) => {
          const { labelKey, icon: CategoryIcon, toneClass } =
            DatasetCategoryDefinitions[category];
          const count = datasetsInNavCategory(groups, category).length;
          const isActiveCategory = category === activeCategory;

          return (
            <li key={category}>
              <CategoryButton
                label={t(labelKey)}
                count={count}
                isActive={isActiveCategory}
                toneClass={toneClass}
                icon={<CategoryIcon className="category-ink size-4 shrink-0" aria-hidden />}
                onHover={setActiveCategory}
                category={category}
              />
            </li>
          );
        })}
      </ul>

      {/* 第二级：右侧知识库列表 */}
      <div className="flex min-w-0 flex-1 flex-col bg-bg-component">
        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {loading ? (
            <div className="flex h-32 items-center justify-center">
              <Spin size="small" />
            </div>
          ) : visibleDatasets.length ? (
            <ul className="space-y-0.5">
              {visibleDatasets.map((dataset) => (
                <DatasetLink
                  key={dataset.id}
                  dataset={dataset}
                  onClick={onNavigate}
                />
              ))}
            </ul>
          ) : (
            <div className="flex h-32 flex-col items-center justify-center gap-1 text-text-secondary">
              <p className="text-sm">{t('datasetCategory.empty')}</p>
            </div>
          )}
        </div>

        {/* 底部固定创建入口：上边 1px 分割线 */}
        <div className="border-t border-panel-border bg-bg-title p-2">
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 text-text-secondary hover:bg-surface-hover hover:text-cable-brand"
            onClick={() => {
              onNavigate();
              navigateToDatasetList({ isCreate: true });
            }}
            data-testid="nav-dataset-new"
          >
            <LucidePlus className="size-4" />
            <span>{t('knowledgeList.createKnowledgeBase')}</span>
          </Button>
        </div>
      </div>
    </div>
  );
}

function CategoryButton({
  category,
  label,
  count,
  isActive,
  toneClass,
  icon,
  onHover,
}: {
  category: DatasetCategory;
  label: string;
  count: number;
  isActive: boolean;
  toneClass: string;
  icon: ReactNode;
  onHover: (category: DatasetCategory) => void;
}) {
  const handleHover = useCallback(() => onHover(category), [category, onHover]);
  const handleFocus = useCallback(() => onHover(category), [category, onHover]);

  return (
    <button
      type="button"
      onMouseEnter={handleHover}
      onFocus={handleFocus}
      aria-current={isActive ? 'true' : undefined}
      data-testid={`nav-dataset-category-${category}`}
      className={cn(
        'flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-sm transition-colors duration-150',
        toneClass,
        isActive
          ? 'bg-surface-hover font-semibold text-text-primary'
          : 'text-text-secondary hover:bg-bg-title hover:text-text-primary',
      )}
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span
        className={cn(
          'shrink-0 text-xs tabular-nums',
          isActive ? 'font-medium text-text-primary' : 'text-text-secondary',
        )}
      >
        {count}
      </span>
    </button>
  );
}

function DatasetLink({
  dataset,
  onClick,
}: {
  dataset: IDataset;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  const { category } = resolveDatasetCategory(dataset);

  return (
    <li>
      <Link
        to={`${Routes.Dataset}/${dataset.id}`}
        onClick={onClick}
        data-testid="nav-dataset-item"
        data-dataset-id={dataset.id}
        className="flex items-center gap-2 px-2.5 py-1.5 text-sm text-text-secondary transition-colors duration-150 hover:bg-surface-hover hover:text-cable-brand"
      >
        <DatasetCategoryIcon category={category} className="size-5 shrink-0" />
        <span className="min-w-0 flex-1 truncate font-medium">{dataset.name}</span>
        <span className="shrink-0 text-xs text-text-secondary/80">
          {dataset.document_count} {t('knowledgeList.doc')}
        </span>
      </Link>
    </li>
  );
}