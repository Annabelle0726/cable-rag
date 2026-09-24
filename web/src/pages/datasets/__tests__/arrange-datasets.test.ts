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
import { arrangeDatasets } from '../arrange-datasets';

const dataset = (id: string) => ({ id, name: id }) as IDataset;

const page = [dataset('a'), dataset('b'), dataset('c'), dataset('d')];

const ids = (datasets: IDataset[]) => datasets.map((item) => item.id);

describe('arrangeDatasets', () => {
  it('leaves the server order alone when nothing is pinned or hidden', () => {
    expect(
      ids(
        arrangeDatasets({
          datasets: page,
          pinnedIds: [],
          hiddenIds: [],
          showHidden: false,
        }),
      ),
    ).toEqual(['a', 'b', 'c', 'd']);
  });

  it('drops hidden datasets from the page', () => {
    expect(
      ids(
        arrangeDatasets({
          datasets: page,
          pinnedIds: [],
          hiddenIds: ['b', 'd'],
          showHidden: false,
        }),
      ),
    ).toEqual(['a', 'c']);
  });

  it('shows hidden datasets again when the viewer asks for them', () => {
    expect(
      ids(
        arrangeDatasets({
          datasets: page,
          pinnedIds: [],
          hiddenIds: ['b'],
          showHidden: true,
        }),
      ),
    ).toEqual(['a', 'b', 'c', 'd']);
  });

  it('promotes pinned datasets to the top, keeping the order inside each group', () => {
    expect(
      ids(
        arrangeDatasets({
          datasets: page,
          pinnedIds: ['d', 'b'],
          hiddenIds: [],
          showHidden: false,
        }),
      ),
    ).toEqual(['b', 'd', 'a', 'c']);
  });

  it('keeps a hidden dataset out even when it is pinned', () => {
    expect(
      ids(
        arrangeDatasets({
          datasets: page,
          pinnedIds: ['c'],
          hiddenIds: ['c'],
          showHidden: false,
        }),
      ),
    ).toEqual(['a', 'b', 'd']);
  });

  it('pins only what is on this page', () => {
    // A pinned id that is not in the page is inert: the page is already the
    // server's answer, so nothing is fetched to fill the gap.
    expect(
      ids(
        arrangeDatasets({
          datasets: page,
          pinnedIds: ['elsewhere'],
          hiddenIds: [],
          showHidden: false,
        }),
      ),
    ).toEqual(['a', 'b', 'c', 'd']);
  });
});
