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

import {
  DatasetCategory,
  DatasetCategoryDefinitions,
  resolveDatasetCategory,
} from '@/constants/dataset-category';
import { IDataset } from '@/interfaces/database/dataset';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';

type DatasetCategoryIconProps = {
  category: DatasetCategory;
  className?: string;
};

/**
 * The class icon in its halo, sized to the 32px slot the card avatar used to
 * occupy so a card's outer box does not change. Sized by the caller when the
 * menu needs a smaller mark.
 */
export function DatasetCategoryIcon({
  category,
  className,
}: DatasetCategoryIconProps) {
  const { icon: Icon, toneClass } = DatasetCategoryDefinitions[category];

  return (
    <span
      className={cn(
        'category-halo flex size-8 shrink-0 items-center justify-center rounded-lg',
        toneClass,
        className,
      )}
    >
      <Icon className="category-ink size-4" aria-hidden />
    </span>
  );
}

type DatasetCategoryChipProps = {
  dataset: Pick<IDataset, 'name' | 'description'> & { category?: string };
  className?: string;
};

/**
 * The class chip shown in the corner of a knowledge-base card. An owner's own
 * tag wins over the class label: the chip shows the text they typed while the
 * icon stays the custom-tag mark.
 */
export function DatasetCategoryChip({
  dataset,
  className,
}: DatasetCategoryChipProps) {
  const { t } = useTranslation();
  const { category, customTag } = resolveDatasetCategory(dataset);
  const { chipKey, icon: Icon, toneClass } = DatasetCategoryDefinitions[category];

  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1 rounded-full border border-cable-hairline px-2 py-0.5 text-xs',
        toneClass,
        className,
      )}
    >
      <Icon className="category-ink size-3" aria-hidden />
      <span className="max-w-[7rem] truncate text-text-secondary">
        {customTag ?? t(chipKey)}
      </span>
    </span>
  );
}
