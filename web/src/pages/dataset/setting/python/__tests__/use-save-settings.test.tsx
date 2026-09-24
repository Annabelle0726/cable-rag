import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSaveSettings } from '../use-save-settings';
const SaveHook = useSaveSettings;
type Values = Parameters<
  ReturnType<typeof SaveHook>['mutateAsync']
>[0]['values'];
const mockUpdate = jest.fn();
const mockAuthorization = jest.fn();
const mockSuccess = jest.fn();
jest.mock('@/services/knowledge-service', () => ({
  updateKb: (...args: unknown[]) => mockUpdate(...args),
  updateDatasetAuthorization: (...args: unknown[]) =>
    mockAuthorization(...args),
}));
jest.mock('@/components/ui/message', () => ({
  __esModule: true,
  default: { success: (...args: unknown[]) => mockSuccess(...args) },
}));
jest.mock('@/hooks/use-knowledge-request', () => ({
  KnowledgeApiAction: {
    FetchKnowledgeDetail: 'fetchKnowledgeDetail',
    FetchKnowledgeListByPage: 'fetchKnowledgeListByPage',
  },
  DatasetAuthorizationKeys: {
    detail: (id: string) => ['fetchDatasetAuthorization', id],
  },
}));
jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const values = {
  name: 'Dataset',
  description: 'Description',
  avatar: '',
  permission: 'custom',
  department_ids: ['department-1'],
  user_ids: ['user-1'],
  parse_type: 1,
  chunk_method: 'naive',
  pipeline_id: 'pipeline-1',
  pipeline_name: 'Display name',
  pipeline_avatar: 'Display avatar',
  parser_config: {
    image_table_context_window: 2,
    enable_children: false,
    children_delimiter: 'child',
  },
} as Values;
function setup() {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(() => useSaveSettings(), { wrapper });
}
beforeEach(() => {
  jest.clearAllMocks();
  mockUpdate.mockResolvedValue({ data: { code: 0 } });
  mockAuthorization.mockResolvedValue({ data: { code: 0 } });
});

it('splits custom authorization from base configuration and preserves the draft', async () => {
  const before = JSON.stringify(values);
  const { result } = setup();
  await act(async () => {
    await result.current.mutateAsync({ datasetId: 'kb-1', values });
  });
  const body = mockUpdate.mock.calls[0][1];
  expect(body).toMatchObject({
    name: 'Dataset',
    description: 'Description',
    avatar: '',
  });
  for (const key of [
    'permission',
    'department_ids',
    'user_ids',
    'pipeline_name',
    'pipeline_avatar',
  ])
    expect(body).not.toHaveProperty(key);
  expect(mockAuthorization).toHaveBeenCalledWith('kb-1', {
    permission: 'custom',
    department_ids: ['department-1'],
    user_ids: ['user-1'],
  });
  expect(mockUpdate.mock.invocationCallOrder[0]).toBeLessThan(
    mockAuthorization.mock.invocationCallOrder[0],
  );
  expect(mockSuccess).toHaveBeenCalledTimes(1);
  expect(JSON.stringify(values)).toBe(before);
});
it.each(['me', 'team'])(
  'saves %s permission exclusively through authorization',
  async (permission) => {
    const { result } = setup();
    await act(async () => {
      await result.current.mutateAsync({
        datasetId: 'kb-1',
        values: { ...values, permission },
      });
    });
    expect(mockUpdate.mock.calls[0][1]).not.toHaveProperty('permission');
    expect(mockAuthorization).toHaveBeenCalledWith('kb-1', {
      permission,
      department_ids: [],
      user_ids: [],
    });
  },
);
it.each([101, 108])(
  'stops before authorization on configuration error %s',
  async (code) => {
    mockUpdate.mockResolvedValue({ data: { code } });
    const { result } = setup();
    await act(async () => {
      await result.current.mutateAsync({ datasetId: 'kb-1', values });
    });
    expect(mockAuthorization).not.toHaveBeenCalled();
    expect(mockSuccess).not.toHaveBeenCalled();
  },
);
it('does not claim success after authorization denial', async () => {
  mockAuthorization.mockResolvedValue({ data: { code: 108 } });
  const { result } = setup();
  await act(async () => {
    await result.current.mutateAsync({ datasetId: 'kb-1', values });
  });
  expect(mockSuccess).not.toHaveBeenCalled();
});
it('keeps the whole two-step save pending until authorization finishes', async () => {
  let finish: (value: unknown) => void = () => {};
  mockAuthorization.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const { result } = setup();
  let pending: Promise<unknown>;
  await act(async () => {
    pending = result.current.mutateAsync({ datasetId: 'kb-1', values });
  });
  await waitFor(() => expect(result.current.isPending).toBe(true));
  expect(mockSuccess).not.toHaveBeenCalled();
  await act(async () => {
    finish({ data: { code: 0 } });
    await pending;
  });
  expect(mockSuccess).toHaveBeenCalledTimes(1);
});

it('allows configuration saves without optional parser settings', async () => {
  const { result } = setup();
  await act(async () => {
    await result.current.mutateAsync({
      datasetId: 'kb-1',
      values: { ...values, parser_config: undefined },
    });
  });
  expect(mockUpdate.mock.calls[0][1].parser_config).toBeUndefined();
  expect(mockSuccess).toHaveBeenCalledTimes(1);
});
