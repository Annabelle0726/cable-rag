import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DatasetCategory } from '@/constants/dataset-category';
import { DatasetDropdown } from '../dataset-dropdown';

const mockSave = jest.fn();
const mockDeleteKnowledge = jest.fn();
const mockShowRename = jest.fn();

jest.mock('@/hooks/use-knowledge-request', () => ({
  useUpdateKnowledge: () => ({
    saveKnowledgeConfiguration: (...args: unknown[]) => mockSave(...args),
    loading: false,
  }),
  useDeleteKnowledge: () => ({
    deleteKnowledge: (...args: unknown[]) => mockDeleteKnowledge(...args),
    loading: false,
  }),
}));

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

// The component binding is read as a value first and only then used in a type,
// because the jest transform rejects an imported binding that appears inside a
// type annotation at all (the same limitation that breaks
// use-manage-values-modal.test.ts upstream).
const DatasetDropdownRef = DatasetDropdown;
type DatasetProp = Parameters<typeof DatasetDropdownRef>[0]['dataset'];

const dataset = {
  id: 'kb-1',
  name: '护套材料技术规格书',
  document_count: 4,
  description: '',
} as unknown as DatasetProp;

const renderDropdown = () =>
  render(
    <DatasetDropdown dataset={dataset} showDatasetRenameModal={mockShowRename}>
      <button type="button" data-testid="dataset-actions">
        actions
      </button>
    </DatasetDropdown>,
  );

// Radix opens a menu from the trigger's keyboard handlers, not from a synthetic
// pointer event (jsdom has no real PointerEvent), so the test drives the menu the
// way a keyboard user does: ArrowDown on the trigger, ArrowRight on the submenu
// trigger, then a click on the item.
const openMenu = async () => {
  fireEvent.keyDown(screen.getByTestId('dataset-actions'), { key: 'ArrowDown' });

  await waitFor(() => {
    expect(screen.getByTestId('dataset-category-menu')).toBeInTheDocument();
  });
};

const openCategorySubmenu = async () => {
  const subTrigger = screen.getByTestId('dataset-category-menu');

  subTrigger.focus();
  fireEvent.keyDown(subTrigger, { key: 'ArrowRight' });

  await waitFor(() => {
    expect(
      screen.getByTestId('dataset-category-set-general'),
    ).toBeInTheDocument();
  });
};

describe('dataset card class menu', () => {
  beforeEach(() => {
    mockSave.mockClear();
  });

  it('offers the industrial classes plus the automatic option', async () => {
    renderDropdown();
    await openMenu();
    await openCategorySubmenu();

    expect(
      screen.getByTestId(`dataset-category-set-${DatasetCategory.Standard}`),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(`dataset-category-set-${DatasetCategory.General}`),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId('dataset-category-set-auto'),
    ).toBeInTheDocument();
  });

  it('stores the chosen class on the dataset', async () => {
    renderDropdown();
    await openMenu();
    await openCategorySubmenu();

    fireEvent.click(screen.getByTestId('dataset-category-set-general'));

    await waitFor(() => {
      expect(mockSave).toHaveBeenCalledWith({
        kb_id: 'kb-1',
        category: DatasetCategory.General,
      });
    });
  });

  it('clears the class when the automatic option is chosen', async () => {
    renderDropdown();
    await openMenu();
    await openCategorySubmenu();

    fireEvent.click(screen.getByTestId('dataset-category-set-auto'));

    await waitFor(() => {
      expect(mockSave).toHaveBeenCalledWith({ kb_id: 'kb-1', category: '' });
    });
  });
});
