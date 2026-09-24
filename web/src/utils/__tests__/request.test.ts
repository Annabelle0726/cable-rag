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
 * The umi-request instance carries the active workspace.
 *
 * `@/utils/request` is the instance every team call goes through (the role
 * change, the removal, the invitation), and it used to be the one transport
 * that never sent `X-Tenant-Id` - so a switch only took effect through the
 * selection the server had stored, a round trip later. The interceptor is
 * asserted directly: nothing here needs a network stack, only the options it
 * hands to `umi-request`.
 */

type RequestInterceptor = (
  url: string,
  options: Record<string, unknown>,
) => { url: string; options: Record<string, any> };

/**
 * Declared before the mocks because the mock factories are hoisted above them;
 * both only read it when a request interceptor actually runs.
 */
let mockActiveTenantId: string | null = null;

jest.mock('umi-request', () => {
  const requestInterceptors: RequestInterceptor[] = [];

  return {
    __requestInterceptors: requestInterceptors,
    extend: () => ({
      interceptors: {
        request: {
          use: (fn: RequestInterceptor) => {
            requestInterceptors.push(fn);
          },
        },
        response: { use: jest.fn() },
      },
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
    }),
  };
});

jest.mock('@/utils/active-tenant', () => ({
  getActiveTenantId: () => mockActiveTenantId,
}));

// The team page's umi-request calls are the subject; nothing here should reach
// the notification stack.
jest.mock('@/utils/notification', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

jest.mock('@/components/ui/message', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

// Importing the module registers its request interceptor.
import '@/utils/request';

const interceptorOptions = (options: Record<string, unknown>) => {
  const registered = (
    jest.requireMock('umi-request') as {
      __requestInterceptors: RequestInterceptor[];
    }
  ).__requestInterceptors;

  expect(registered).toHaveLength(1);

  return registered[0]('/api/v1/tenants', options).options;
};

describe('the umi-request interceptor', () => {
  beforeEach(() => {
    mockActiveTenantId = null;
  });

  it('sends the active workspace as X-Tenant-Id', () => {
    mockActiveTenantId = 'tenant-joined';

    const options = interceptorOptions({ headers: {} });

    expect(options.headers['X-Tenant-Id']).toBe('tenant-joined');
  });

  it('sends no workspace header when none is stored', () => {
    const options = interceptorOptions({ headers: {} });

    expect(options.headers).not.toHaveProperty('X-Tenant-Id');
  });

  it('keeps the authorization header alongside it', () => {
    mockActiveTenantId = 'tenant-joined';

    const options = interceptorOptions({ headers: {} });

    expect(options.headers.Authorization).toBeDefined();
  });

  it('lets an explicit per-call header win', () => {
    mockActiveTenantId = 'tenant-joined';

    const options = interceptorOptions({
      headers: { 'X-Tenant-Id': 'tenant-chosen-by-the-caller' },
    });

    expect(options.headers['X-Tenant-Id']).toBe('tenant-chosen-by-the-caller');
  });
});
