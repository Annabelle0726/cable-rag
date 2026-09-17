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
import { PropsWithChildren } from 'react';

type CardContainerProps = { className?: string } & PropsWithChildren;

/**
 * The one card grid: every card list in the app renders inside it, so a card on a
 * home section is exactly the size of the same card on its list page.
 *
 * Rows are left to their contents on purpose. The uniform card size comes from the
 * card itself — `HomeCard` is a fixed 112px and the see-all and create tiles match
 * it — rather than from the grid, because sizing rows to the tallest card would
 * stretch every card in the grid as soon as one of them carried an extra line.
 * Cards that want a different size (compilation templates, skills) keep it.
 */
export function CardContainer({ children, className }: CardContainerProps) {
  return (
    <div
      className={cn(
        'grid auto-rows-auto grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 content-start',
        // The list pages scroll this grid, and paginating from a full page to a
        // short one removes the scrollbar: reserving its width keeps the columns
        // from jumping sideways between pages.
        'scrollbar-gutter-stable',
        className,
      )}
    >
      {children}
      <div className="col-span-full h-6" aria-hidden="true" />
    </div>
  );
}
