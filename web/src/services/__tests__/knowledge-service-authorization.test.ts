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

/**
 * The request shapes the dataset authorization endpoints depend on.
 *
 * `@/utils/request` is umi-request: the body has to be nested under `data`, or
 * the route reports the fields as missing (`code=101`) and the grant is never
 * written.
 */

const mockGet = jest.fn((..._args: unknown[]) =>
  Promise.resolve({ data: { code: 0, data: {} } }),
);
const mockPut = jest.fn((..._args: unknown[]) =>
  Promise.resolve({ data: { code: 0, data: {} } }),
);

jest.mock('@/utils/request', () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    put: (...args: unknown[]) => mockPut(...args),
    post: jest.fn(),
    delete: jest.fn(),
  },
}));

import {
  getDatasetAuthorization,
  updateDatasetAuthorization,
} from '../knowledge-service';

describe('dataset authorization request shapes', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('reads the authorization from the dataset path', () => {
    getDatasetAuthorization('kb-1');

    expect(mockGet).toHaveBeenCalledWith(
      expect.stringContaining('/datasets/kb-1/authorization'),
    );
  });

  it('nests the whole authorization body under `data`', () => {
    const body = {
      permission: 'custom',
      department_ids: ['dept-1'],
      user_ids: ['user-1'],
    };

    updateDatasetAuthorization('kb-1', body);

    expect(mockPut).toHaveBeenCalledWith(
      expect.stringContaining('/datasets/kb-1/authorization'),
      { data: body },
    );
  });

  it('sends empty subject lists for a mode that has no subjects', () => {
    updateDatasetAuthorization('kb-1', {
      permission: 'team',
      department_ids: [],
      user_ids: [],
    });

    expect(mockPut).toHaveBeenCalledWith(
      expect.stringContaining('/datasets/kb-1/authorization'),
      { data: { permission: 'team', department_ids: [], user_ids: [] } },
    );
  });
});
