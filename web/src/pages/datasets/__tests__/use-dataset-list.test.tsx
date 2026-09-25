import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { arrangeDatasets } from '../arrange-datasets';
import { fetchAccessibleDatasets, useDatasetList } from '../use-dataset-list';

const fetchList = fetchAccessibleDatasets;
const useList = useDatasetList;
const mockList = jest.fn();
let mockTenant = 'workspace-a';
let mockUser = 'user-a';
jest.mock('@/services/knowledge-service', () => ({
  listDataset: (...args: unknown[]) => mockList(...args),
}));
jest.mock('@/utils/active-tenant', () => ({
  getActiveTenantId: () => mockTenant,
}));
jest.mock('@/hooks/use-user-setting-request', () => ({
  useFetchUserInfo: () => ({ data: { id: mockUser } }),
}));
jest.mock('@/hooks/use-knowledge-request', () => ({
  KnowledgeApiAction: { FetchKnowledgeListByPage: 'list' },
}));
jest.mock('@/components/list-filter-bar/use-handle-filter-submit', () => ({
  useHandleFilterSubmit: () => ({ filterValue: {} }),
}));

beforeEach(() => {
  mockList.mockReset();
  mockTenant = 'workspace-a';
  mockUser = 'user-a';
});

it('assembles only authorized server pages before UI sorting', async () => {
  const rows = Array.from({ length: 100 }, (_, i) => ({ id: String(i) }));
  mockList
    .mockResolvedValueOnce({ data: { code: 0, data: rows, total: 101 } })
    .mockResolvedValueOnce({
      data: { code: 0, data: [{ id: 'last-page-pin' }], total: 101 },
    });
  const result = await fetchList(mockTenant, [], new AbortController().signal);
  expect(result).toHaveLength(101);
  expect(
    arrangeDatasets({
      datasets: result,
      pinnedIds: ['last-page-pin', 'denied-id'],
      hiddenIds: [],
      showHidden: false,
    })
      .slice(0, 1)
      .map((row) => row.id),
  ).toEqual(['last-page-pin']);
  expect(mockList).toHaveBeenLastCalledWith({
    page: 2,
    page_size: 100,
    owner_ids: [],
  });
});

it('discards all accumulated metadata when permission is denied on a later page', async () => {
  mockList
    .mockResolvedValueOnce({
      data: {
        code: 0,
        data: Array.from({ length: 100 }, (_, i) => ({ id: String(i) })),
        total: 101,
      },
    })
    .mockResolvedValueOnce({ data: { code: 108 } });
  expect(await fetchList(mockTenant, [], new AbortController().signal)).toEqual(
    [],
  );
});

it('never reuses dataset rows across workspace or account changes', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: React.PropsWithChildren) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  mockList.mockResolvedValueOnce({
    data: { code: 0, data: [{ id: 'private-a' }], total: 1 },
  });
  const { result, rerender } = renderHook(() => useList(), { wrapper });
  await waitFor(() => expect(result.current.kbs).toHaveLength(1));
  mockList.mockResolvedValue({ data: { code: 108 } });
  mockTenant = 'workspace-b';
  rerender();
  expect(result.current.kbs).toEqual([]);
  await waitFor(() => expect(result.current.loading).toBe(false));
  mockUser = 'user-b';
  rerender();
  expect(result.current.kbs).toEqual([]);
});
