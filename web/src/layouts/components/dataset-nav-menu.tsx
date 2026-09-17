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

/** Wait before closing, so a pointer crossing the gap into the panel survives. */
const CloseDelayMs = 160;
/** The menu is a directory, not a browser: one long page is enough. */
const MenuPageSize = 100;

type DatasetNavMenuProps = {
  to: string;
  label: string;
  icon: LucideIcon;
  isActive: boolean;
  className?: string;
  testId?: string;
};

/**
 * The knowledge-base entry of the top navigation: a two-level menu where the
 * first level is the plant's industrial classification and the second lists that
 * class's knowledge bases, with a create shortcut pinned below.
 *
 * The trigger is still the navigation link — clicking it opens the list page as
 * before — while hovering (or focusing) opens the menu, and the panel closes on
 * a route change so it never lingers over the page it navigated to.
 */
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
    // The panel is opened by hovering, so stealing focus would look like the
    // page jumped while the pointer is still on the navigation bar.
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
          className={className}
          onMouseEnter={handleOpen}
          onMouseLeave={scheduleClose}
          onFocus={handleOpen}
          onClick={scheduleClose}
        >
          <Icon className="size-4 shrink-0 stroke-[1.75]" />
          <span>{label}</span>
        </Link>
      </PopoverTrigger>

      <PopoverContent
        align="start"
        sideOffset={10}
        onMouseEnter={cancelClose}
        onMouseLeave={scheduleClose}
        onOpenAutoFocus={handlePreventAutoFocus}
        className="glass-panel w-[min(92vw,34rem)] rounded-2xl p-0"
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
    <div className="flex min-h-[13rem]">
      {/* First level: the industrial classification. */}
      <ul
        className="w-[11.5rem] shrink-0 space-y-0.5 border-r border-cable-hairline p-2"
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
                icon={<CategoryIcon className="category-ink size-4" aria-hidden />}
                onHover={setActiveCategory}
                category={category}
              />
            </li>
          );
        })}
      </ul>

      {/* Second level: the knowledge bases of the highlighted class. */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {loading ? (
            <div className="flex h-24 items-center justify-center">
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
            <p className="px-2 py-6 text-center text-sm text-text-secondary">
              {t('datasetCategory.empty')}
            </p>
          )}
        </div>

        <div className="border-t border-cable-hairline p-2">
          <Button
            variant="ghost"
            className="w-full justify-start gap-2"
            onClick={() => {
              onNavigate();
              navigateToDatasetList({ isCreate: true });
            }}
            data-testid="nav-dataset-new"
          >
            <LucidePlus className="size-4" />
            {t('knowledgeList.createKnowledgeBase')}
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
        'flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition-colors duration-200 ease-in-out',
        toneClass,
        isActive
          ? 'bg-cable-nav-active-bg font-medium text-text-primary'
          : 'text-text-secondary hover:bg-cable-nav-active-bg hover:text-text-primary',
      )}
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span className="shrink-0 text-xs text-text-secondary">{count}</span>
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
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-text-secondary transition-colors duration-200 ease-in-out hover:bg-cable-nav-active-bg hover:text-text-primary"
      >
        <DatasetCategoryIcon category={category} className="size-5 rounded-md" />
        <span className="min-w-0 flex-1 truncate">{dataset.name}</span>
        <span className="shrink-0 text-xs">
          {dataset.document_count} {t('knowledgeList.doc')}
        </span>
      </Link>
    </li>
  );
}
