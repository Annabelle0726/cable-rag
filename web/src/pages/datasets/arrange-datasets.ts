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

import { IDataset } from '@/interfaces/database/dataset';

/**
 * Apply the viewer's own ordering to a page of datasets.
 *
 * Hidden datasets are dropped unless the viewer asked to see them, and pinned
 * ones move to the top. The order the server returned is preserved inside both
 * groups, so the page's sort stays the user's chosen one and pinning only
 * promotes a subset of it.
 *
 * Hiding is a per-user preference, never an authorization decision: the rows the
 * server sends are already the ones this user may read, so dropping one here
 * changes nothing but this view.
 */
export const arrangeDatasets = ({
  datasets,
  pinnedIds,
  hiddenIds,
  showHidden,
}: {
  datasets: IDataset[];
  pinnedIds: string[];
  hiddenIds: string[];
  showHidden: boolean;
}): IDataset[] => {
  const pinned = new Set(pinnedIds);
  const hidden = new Set(hiddenIds);
  const visible = showHidden
    ? datasets
    : datasets.filter((dataset) => !hidden.has(dataset.id));

  if (pinned.size === 0) {
    return visible;
  }

  return [
    ...visible.filter((dataset) => pinned.has(dataset.id)),
    ...visible.filter((dataset) => !pinned.has(dataset.id)),
  ];
};
