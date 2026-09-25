import { act, render, screen } from '@testing-library/react';
import { useDatasetPreferencesStore } from '@/hooks/use-dataset-preferences';
import { Datasets } from '../datasets';

const HomeDatasets = Datasets;
const preferences = useDatasetPreferencesStore;
jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock('@/hooks/use-user-setting-request', () => ({
  useFetchUserInfo: () => ({ data: { id: 'viewer' } }),
}));
jest.mock('../../datasets/use-dataset-list', () => ({
  useDatasetList: () => ({
    kbs: [
      { id: 'a', name: 'A', update_time: 3 },
      { id: 'b', name: 'B', update_time: 2 },
      { id: 'c', name: 'C', update_time: 1 },
    ],
    loading: false,
  }),
}));
jest.mock('../../datasets/dataset-table', () => ({
  DatasetTable: ({ datasets }: { datasets: { id: string }[] }) => (
    <div data-testid="rows">{datasets.map((row) => row.id).join(',')}</div>
  ),
}));
jest.mock('../../datasets/query-panel', () => ({
  DatasetQueryPanel: () => null,
}));
jest.mock('../../datasets/use-rename-dataset', () => ({
  useRenameDataset: () => ({}),
}));
jest.mock('@/components/rename-dialog', () => ({ RenameDialog: () => null }));
jest.mock('@/hooks/logic-hooks/navigate-hooks', () => ({
  useNavigatePage: () => ({ navigateToDatasetList: jest.fn() }),
}));
jest.mock('../home-layout', () => ({ SectionHeading: () => null }));

it('immediately follows personal hide, restore and pin changes without leaking absent IDs', () => {
  preferences.setState({
    byUser: { viewer: { pinned: ['unauthorized', 'c'], hidden: ['b'] } },
    showHidden: true,
  });
  render(<HomeDatasets />);
  expect(screen.getByTestId('rows')).toHaveTextContent('c,a');
  act(() => preferences.getState().toggleHidden('viewer', 'c'));
  expect(screen.getByTestId('rows')).toHaveTextContent(/^a$/);
  expect(preferences.getState().byUser.viewer.pinned).not.toContain('c');
  act(() => preferences.getState().toggleHidden('viewer', 'b'));
  expect(screen.getByTestId('rows')).toHaveTextContent('a,b');
  act(() => preferences.getState().togglePinned('viewer', 'b'));
  expect(screen.getByTestId('rows')).toHaveTextContent('b,a');
});
