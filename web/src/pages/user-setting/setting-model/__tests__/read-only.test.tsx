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

import { fireEvent, render, screen } from '@testing-library/react';

import { TooltipProvider } from '@/components/ui/tooltip';
import { TenantRole } from '@/pages/user-setting/constants';
import SettingModelV2 from '../index';

/**
 * A tenant member must not be offered a model-settings write affordance: every
 * mutating model endpoint is `@require_tenant_admin`, so an enabled control
 * would only produce a 403. These tests pin the read-only surface itself
 * (banner, Save, add-instance, default-model select) rather than the server
 * guard, which is covered by `test/unit_test/api/apps/test_provider_rbac_coverage.py`.
 */

let mockRole: string | undefined;
let mockDefaultModelSelectDisabled: boolean[] = [];

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock('@/hooks/common-hooks', () => ({
  useTranslate: () => ({ t: (key: string) => key }),
}));

// jsdom implements no `CSS.supports`, and this module evaluates it at import
// time, so the whole provider-config chain would abort before rendering.
jest.mock('@/utils/css-support', () => ({ supportsCssAnchor: false }));

jest.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
}));

jest.mock('@/hooks/use-user-setting-request', () => ({
  useFetchUserInfo: () => ({ data: { role: mockRole } }),
}));

jest.mock('@/hooks/use-llm-request', () => ({
  LlmKeys: { providerInstances: (name: string) => ['instances', name] },
  useFetchAddedProviders: () => ({
    data: [{ name: 'OpenAI', has_instance: true }],
  }),
  useFetchProviderInstances: () => ({
    data: [{ instance_name: 'primary', id: 'instance-1' }],
    loading: false,
  }),
  useAddProviderInstance: () => ({ addProviderInstance: jest.fn() }),
  useUpdateProviderInstance: () => ({ updateProviderInstance: jest.fn() }),
  useFetchDefaultModelDictionary: () => ({ llm_id: '' }),
  useSetDefaultModel: () => ({ setDefaultModel: jest.fn() }),
}));

// The provider rail is just the way to reach a provider pane; a button keeps the
// test focused on the read-only surface rather than on provider navigation.
jest.mock('../layout/sidebar', () => ({
  Sidebar: ({ onSelect }: { onSelect: (value: string) => void }) => (
    <button
      type="button"
      data-testid="select-provider"
      onClick={() => onSelect('OpenAI')}
    >
      OpenAI
    </button>
  ),
}));

// The page drives each card through an imperative ref, so the stub has to
// forward one to avoid React's "Function components cannot be given refs".
jest.mock('../instance-card/provider-instance-card', () => ({
  ProviderInstanceCard: jest
    .requireActual('react')
    .forwardRef(() => <div data-testid="instance-card" />),
}));

// `ModelTreeSelect` is the whole editable surface of the default-models pane, so
// rendering it as a disabled-aware stub is what makes that pane assertable.
jest.mock('@/components/model-tree-select', () => ({
  ModelTypeMap: { llm_id: ['chat'] },
  ModelTreeSelect: ({ disabled }: { disabled?: boolean }) => {
    mockDefaultModelSelectDisabled.push(Boolean(disabled));
    return <div data-testid="model-tree-select" />;
  },
}));

// The page normally sits under the app shell's `TooltipProvider`, which the
// default-models pane's field labels rely on.
const renderPage = () =>
  render(
    <TooltipProvider>
      <SettingModelV2 />
    </TooltipProvider>,
  );

const selectProvider = () => {
  fireEvent.click(screen.getByTestId('select-provider'));
};

describe('setting-model read-only surface', () => {
  beforeEach(() => {
    mockDefaultModelSelectDisabled = [];
  });

  describe('as a tenant member', () => {
    beforeEach(() => {
      mockRole = TenantRole.Normal;
    });

    it('explains through the banner why the configuration is not editable', () => {
      renderPage();

      expect(
        screen.getByTestId('model-settings-readonly-notice'),
      ).toBeInTheDocument();
    });

    it('drops the batch Save and the add-instance affordances', () => {
      renderPage();
      selectProvider();

      expect(screen.queryByTestId('provider-save-all')).not.toBeInTheDocument();
      expect(
        screen.queryByTestId('add-instance-bottom'),
      ).not.toBeInTheDocument();
      // The instance itself stays visible: the page is a viewing surface.
      expect(screen.getByTestId('instance-card')).toBeInTheDocument();
    });

    it('renders every default-model select read-only', () => {
      renderPage();

      expect(screen.getAllByTestId('model-tree-select')).toHaveLength(6);
      expect(mockDefaultModelSelectDisabled).not.toHaveLength(0);
      expect(mockDefaultModelSelectDisabled.every(Boolean)).toBe(true);
    });
  });

  describe('as the tenant owner', () => {
    beforeEach(() => {
      mockRole = TenantRole.Owner;
    });

    it('shows no banner and keeps every write affordance', () => {
      renderPage();
      selectProvider();

      expect(
        screen.queryByTestId('model-settings-readonly-notice'),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId('provider-save-all')).toBeInTheDocument();
      expect(screen.getByTestId('add-instance-bottom')).toBeInTheDocument();
    });

    it('renders every default-model select editable', () => {
      renderPage();

      expect(mockDefaultModelSelectDisabled).not.toHaveLength(0);
      expect(mockDefaultModelSelectDisabled.some(Boolean)).toBe(false);
    });
  });

  describe('when the server reports no role', () => {
    beforeEach(() => {
      mockRole = undefined;
    });

    it('stays editable rather than locking the owner out', () => {
      renderPage();
      selectProvider();

      expect(
        screen.queryByTestId('model-settings-readonly-notice'),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId('provider-save-all')).toBeInTheDocument();
    });
  });
});
