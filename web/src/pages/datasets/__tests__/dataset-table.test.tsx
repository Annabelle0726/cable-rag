import { render, screen } from '@testing-library/react';
import { DatasetTable } from '../dataset-table';

const TableComponent = DatasetTable;
type Dataset = Parameters<typeof TableComponent>[0]['datasets'][number];
let mockPinned = true;
jest.mock('@/hooks/use-dataset-preferences', () => ({
  useDatasetPreferences: () => ({ isPinned: () => mockPinned }),
}));
jest.mock('@/hooks/logic-hooks/navigate-hooks', () => ({
  useNavigatePage: () => ({ navigateToDataset: () => jest.fn() }),
}));
jest.mock('../dataset-dropdown', () => ({ DatasetDropdown: () => null }));
jest.mock('@/components/shared-badge', () => ({ SharedBadge: () => null }));
jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

it.each([
  ['team', 'team'],
  ['me', 'private'],
  ['custom', 'custom'],
])('shows %s visibility and persistent pin state', (permission, label) => {
  const datasets = [
    {
      id: 'kb-1',
      name: 'Dataset',
      status: '1',
      permission,
      update_time: 0,
      document_count: 2,
    },
  ] as Dataset[];
  mockPinned = true;
  const { rerender } = render(
    <DatasetTable datasets={datasets} showDatasetRenameModal={jest.fn()} />,
  );
  expect(screen.getByTestId('dataset-pinned-badge')).toHaveTextContent(
    'listVisibility.pinned',
  );
  expect(screen.getByText(`listVisibility.${label}`)).toBeInTheDocument();
  mockPinned = false;
  rerender(
    <DatasetTable datasets={datasets} showDatasetRenameModal={jest.fn()} />,
  );
  expect(screen.queryByTestId('dataset-pinned-badge')).not.toBeInTheDocument();
});

it('shows only hidden status even when the backend dataset is available', () => {
  const datasets = [
    {
      id: 'kb-1',
      name: 'Dataset',
      status: '1',
      permission: 'team',
      update_time: 0,
      document_count: 2,
    },
  ] as Dataset[];
  const { rerender } = render(
    <DatasetTable
      datasets={datasets}
      hiddenDatasetIds={['kb-1']}
      showDatasetRenameModal={jest.fn()}
    />,
  );
  expect(screen.getByTestId('dataset-status')).toHaveTextContent(
    'common.hiddenBadge',
  );
  expect(screen.queryByText('datasetTable.available')).not.toBeInTheDocument();
  expect(screen.getAllByText('common.hiddenBadge')).toHaveLength(1);
  rerender(
    <DatasetTable
      datasets={datasets}
      hiddenDatasetIds={[]}
      showDatasetRenameModal={jest.fn()}
    />,
  );
  expect(screen.getByTestId('dataset-status')).toHaveTextContent(
    'datasetTable.available',
  );
});
