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
            'relative duration-150 data-[state=open]:rounded-b-none data-[state=open]:bg-cable-nav-active-bg data-[state=open]:text-text-primary',
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
              className="absolute inset-x-0 top-full z-10 bg-cable-nav-active-bg"
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
        /* 改动重点：
           1. 统一采用 border-cable-hairline 细线边框，避免粗糙黑框。
           2. 使用 bg-bg-card 提高背景不透明度与深度，搭配 shadow-2xl 与 backdrop-blur-md，告别灰蒙感。
           3. 移除了无谓的平铺内边距，完全交由内部 Grid/Flex 控制。
        */
        className={cn(
          'z-50 w-[min(92vw,34rem)] overflow-hidden outline-none',
          'rounded-t-none rounded-b-2xl border border-cable-hairline bg-bg-card/95 shadow-2xl backdrop-blur-md p-0',
          'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
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
      {/* 第一级：左侧分类列 - 背景使用纯净微透明色，保持直角相接 */}
      <ul
        className="w-[11.5rem] shrink-0 space-y-1 bg-bg-base/40 p-2"
        role="list"
      >
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
      <div className="flex min-w-0 flex-1 flex-col bg-bg-card">
        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {loading ? (
            <div className="flex h-32 items-center justify-center">
              <Spin size="small" />
            </div>
          ) : visibleDatasets.length ? (
            <ul className="space-y-1">
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

        {/* 底部固定创建按钮：增加微光悬浮与分割线 */}
        <div className="border-t border-cable-hairline bg-bg-base/20 p-2">
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 text-text-secondary hover:bg-cable-nav-active-bg hover:text-text-primary"
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
        'flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-sm transition-all duration-150',
        toneClass,
        isActive
          ? 'bg-cable-nav-active-bg font-semibold text-text-primary shadow-sm'
          : 'text-text-secondary hover:bg-cable-nav-active-bg/60 hover:text-text-primary',
      )}
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span className={cn(
        'shrink-0 text-xs rounded-full px-1.5 py-0.2',
        isActive ? 'text-text-primary font-medium' : 'text-text-secondary'
      )}>
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
        className="flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm text-text-secondary transition-all duration-150 hover:bg-cable-nav-active-bg hover:text-text-primary"
      >
        <DatasetCategoryIcon category={category} className="size-5 rounded-lg shrink-0" />
        <span className="min-w-0 flex-1 truncate font-medium">{dataset.name}</span>
        <span className="shrink-0 text-xs text-text-secondary/80">
          {dataset.document_count} {t('knowledgeList.doc')}
        </span>
      </Link>
    </li>
  );
}