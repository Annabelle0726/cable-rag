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
import { TagFilterButtonProps } from '../interface';

/** Tag pill used in the filter row. */
export function TagFilterButton({
  label,
  count,
  active,
  onClick,
}: TagFilterButtonProps) {
  return (
    <button
      type="button"
      className={cn(
        'px-2.5 py-1 text-xs rounded-full',
        // The selected tag is the page's brand fill, the rest are mini ceramic
        // badges: neither state paints the ink or a flat grey chip any more.
        active ? 'ceramic-cta' : 'ceramic-badge hover:text-text-primary',
      )}
      onClick={onClick}
    >
      {label}
      <span className="ml-1 opacity-60">{count}</span>
    </button>
  );
}
