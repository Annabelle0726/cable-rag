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
 * The request shapes the team endpoints depend on.
 *
 * `@/utils/request` is umi-request: the payload has to be nested under `data`.
 * Passing it as the second argument sends the request with **no body at all**,
 * which the route reports as "required argument are missing: <field>" - the
 * failure that made role changes and workspace switches impossible from the UI
 * while the same calls succeeded when issued by hand.
 */

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPut = jest.fn();
const mockDelete = jest.fn();

jest.mock('@/utils/request', () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
  // Mirrors the real helper, which nests the body under `data`.
  post: (url: string, body: unknown) => mockPost(url, { data: body }),
}));

import {
  addTenantUser,
  deleteTenantUser,
  setActiveTenant,
  updateTenantUserRole,
} from '../user-service';

describe('user-service request shapes', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('sends the role under `data` so the route can validate it', () => {
    updateTenantUserRole({
      tenantId: 'tenant-1',
      userId: 'user-2',
      role: 'admin',
    });

    expect(mockPut).toHaveBeenCalledWith(
      expect.stringContaining('/tenants/tenant-1/users/user-2/role'),
      { data: { role: 'admin' } },
    );
  });

  it('sends the workspace switch under `data`', () => {
    setActiveTenant('tenant-1');

    expect(mockPut).toHaveBeenCalledWith(
      expect.stringContaining('/users/me/tenant'),
      { data: { tenantId: 'tenant-1' } },
    );
  });

  it('sends the removed member under `data`', () => {
    deleteTenantUser({ tenantId: 'tenant-1', userId: 'user-2' });

    expect(mockDelete).toHaveBeenCalledWith(
      expect.stringContaining('/tenants/tenant-1/users'),
      { data: { userId: 'user-2' } },
    );
  });

  it('carries the role on an invitation', () => {
    // `department_id` and `title` are optional in the contract: a call that
    // supplies no profile must not put them on the wire at all, or the payload
    // stops matching the shape the route documents.
    addTenantUser('tenant-1', 'someone@example.com', 'admin');

    const [url, options] = mockPost.mock.calls[0] as [string, any];
    expect(url).toContain('/tenants/tenant-1/users');
    expect(options.data).toEqual({
      email: 'someone@example.com',
      role: 'admin',
    });
  });

  it('sends the department and title a caller did choose', () => {
    addTenantUser('tenant-1', 'someone@example.com', 'normal', {
      departmentId: 'department-1',
      title: 'Sales manager',
    });

    const [, options] = mockPost.mock.calls[0] as [string, any];
    expect(options.data).toEqual({
      email: 'someone@example.com',
      role: 'normal',
      departmentId: 'department-1',
      title: 'Sales manager',
    });
  });
});
