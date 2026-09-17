/*
 *  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
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

import { cn } from '@/lib/utils';
import { Funnel } from 'lucide-react';
import React, {
  ChangeEventHandler,
  PropsWithChildren,
  ReactNode,
  useMemo,
} from 'react';
import { HomeIcon } from '../svg-icon';
import { Button, ButtonProps } from '../ui/button';
import { SearchInput } from '../ui/input';
import { CheckboxFormMultipleProps, FilterPopover } from './filter-popover';

interface IProps {
  title?: ReactNode;
  searchString?: string;
  onSearchChange?: ChangeEventHandler<HTMLInputElement>;
  showFilter?: boolean;
  showSearch?: boolean;
  leftPanel?: ReactNode;
  preChildren?: ReactNode;
}

export const FilterButton = React.forwardRef<
  HTMLButtonElement,
  ButtonProps & { count?: number }
>(({ count = 0, ...props }, ref) => {
  return (
    <Button
      // Raised glass capsule on the same 40px rail as the search field and the
      // page's create button, with the funnel in the secondary ink rather than
      // the primitive's ink-white. `size="auto"` keeps the primitive from
      // imposing its own box, so the geometry comes from these utilities alone.
      className={cn(
        'ceramic-relief h-10 shrink-0 rounded-full text-text-secondary hover:text-text-primary',
        count > 0 ? 'px-4' : 'w-10 px-0',
      )}
      size="auto"
      {...props}
      ref={ref}
    >
      <Funnel />

      {count > 0 && (
        <span className="rounded bg-text-badge px-1 py-0.5 text-xs leading-none text-text-primary">
          {count}
        </span>
      )}
    </Button>
  );
});

FilterButton.displayName = 'FilterButton';

export default function ListFilterBar({
  title,
  children,
  preChildren,
  searchString,
  onSearchChange,
  showFilter = true,
  showSearch = true,
  leftPanel,
  value,
  onChange,
  onOpenChange,
  filters,
  className,
  icon,
  iconClassName,
  filterGroup,
  searchVariant = 'default',
}: PropsWithChildren<IProps & Omit<CheckboxFormMultipleProps, 'setOpen'>> & {
  className?: string;
  icon?: ReactNode;
  iconClassName?: string;
  filterGroup?: Record<string, string[]>;
  /**
   * `capsule` dresses the search field as the ceramic pill the file manager
   * uses: a translucent surface, the shared hairline, an accent glow on focus
   * and the magnifier inked in the secondary content colour.
   */
  searchVariant?: 'default' | 'capsule';
}) {
  const filterCount = useMemo(() => {
    return typeof value === 'object' && value !== null
      ? Object.values(value).reduce((pre, cur) => {
          if (Array.isArray(cur)) {
            return pre + cur.length;
          }
          if (typeof cur === 'object') {
            return (
              pre +
              Object.values(cur).reduce((pre, cur) => {
                return pre + (cur?.length || 0);
              }, 0)
            );
          }
          return pre;
        }, 0)
      : 0;
  }, [value]);

  const hasFilter = Boolean(filters?.length && showFilter);

  return (
    <div
      className={cn(
        'flex min-w-0 flex-col gap-3 md:flex-row md:items-center md:justify-between',
        className,
      )}
    >
      <h1 className="flex min-w-0 shrink-0 items-center gap-2.5 text-2xl font-semibold">
        {typeof icon === 'string' ? (
          <HomeIcon
            name={`${icon}`}
            imgClass={cn('size-[1em]', iconClassName)}
          />
        ) : (
          icon
        )}
        {leftPanel || title}
      </h1>

      <div
        className={cn(
          // One control row on every list page: centred on the 40px rail and
          // pushed to the right edge, so switching pages never moves the create
          // button sideways or up.
          'min-w-0 w-full items-center gap-3',
          preChildren
            ? 'flex flex-wrap md:flex-nowrap md:w-auto md:shrink-0 md:justify-end'
            : cn(
                'grid',
                hasFilter
                  ? 'grid-cols-[auto_minmax(0,1fr)_auto]'
                  : 'grid-cols-[minmax(0,1fr)_auto]',
                'md:flex md:w-auto md:shrink-0 md:justify-end',
              ),
        )}
        role="toolbar"
      >
        {preChildren}
        {hasFilter && (
          <FilterPopover
            value={value}
            onChange={onChange}
            filters={filters}
            filterGroup={filterGroup}
            onOpenChange={onOpenChange}
          >
            <FilterButton count={filterCount} />
          </FilterPopover>
        )}
        {showSearch && (
          <SearchInput
            value={searchString}
            onChange={onSearchChange}
            className={cn(
              'min-w-0 w-full',
              preChildren ? 'flex-1 basis-32' : '',
              'md:w-32',
              searchVariant === 'capsule' &&
                'ceramic-relief h-10 rounded-full px-4 placeholder:text-content-secondary',
            )}
            rootClassName={
              searchVariant === 'capsule'
                ? '[&>span]:text-content-secondary'
                : undefined
            }
            role="searchbox"
          />
        )}

        {children && (
          <div className="shrink-0 justify-self-end">{children}</div>
        )}
      </div>
    </div>
  );
}
