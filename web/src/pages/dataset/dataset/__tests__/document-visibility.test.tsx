import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DatasetActionCell } from '../dataset-action-cell';
const ActionCell = DatasetActionCell;
type DocumentRecord = Parameters<typeof ActionCell>[0]['record'];

jest.mock('@/components/confirm-delete-dialog', () => ({
  ConfirmDeleteDialog: ({ children }: { children: React.ReactNode }) =>
    children,
}));
const mockSetStatus = jest.fn();
let mockCanManage = true;
let mockLoading = false;
let mockRunning = false;
jest.mock('@/hooks/use-document-request', () => ({
  useSetDocumentStatus: () => ({
    setDocumentStatus: mockSetStatus,
    loading: mockLoading,
  }),
  useRemoveDocument: () => ({ removeDocument: jest.fn() }),
}));
jest.mock('@/hooks/use-can-manage-dataset', () => ({
  useCanManageDataset: () => mockCanManage,
}));
jest.mock('../../contexts/knowledge-base-context', () => ({
  useKnowledgeBaseContext: () => ({ knowledgeBase: {} }),
}));
jest.mock('../utils', () => ({ isDocumentProcessing: () => mockRunning }));
jest.mock('@/services/file-manager-service', () => ({
  downloadDatasetDocument: jest.fn(),
}));
jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

function renderFile(status = '1') {
  const record = {
    id: 'doc-1',
    dataset_id: 'kb-1',
    name: 'file.pdf',
    type: 'pdf',
    status,
  } as DocumentRecord;
  return render(
    <DatasetActionCell
      record={record}
      showRenameModal={jest.fn()}
      setRowSelection={jest.fn()}
    />,
  );
}

beforeEach(() => {
  mockCanManage = true;
  mockLoading = false;
  mockRunning = false;
  mockSetStatus.mockReset().mockResolvedValue({ code: 0 });
});

it.each([
  ['1', false, 'hideFile'],
  ['0', true, 'restoreFile'],
])(
  'changes server retrieval state for status %s',
  async (status, enabled, label) => {
    renderFile(status as string);
    fireEvent.click(
      screen.getByRole('button', { name: `listVisibility.${label}` }),
    );
    await waitFor(() =>
      expect(mockSetStatus).toHaveBeenCalledWith({
        documentId: 'doc-1',
        datasetId: 'kb-1',
        status: enabled,
      }),
    );
  },
);

it('does not allow a read-only viewer to change visibility', () => {
  mockCanManage = false;
  renderFile();
  const button = screen.getByTestId('document-toggle-visibility');
  expect(button).toBeDisabled();
  fireEvent.click(button);
  expect(mockSetStatus).not.toHaveBeenCalled();
});

it('disables changes while saving or parsing', () => {
  mockLoading = true;
  const { unmount } = renderFile();
  expect(screen.getByTestId('document-toggle-visibility')).toBeDisabled();
  unmount();
  mockLoading = false;
  mockRunning = true;
  renderFile();
  expect(screen.getByTestId('document-toggle-visibility')).toBeDisabled();
});

it.each([108, 102])(
  'preserves visibility when the backend rejects with code %s',
  async (code) => {
    mockSetStatus.mockResolvedValue({ code });
    renderFile();
    fireEvent.click(screen.getByTestId('document-toggle-visibility'));
    await waitFor(() => expect(mockSetStatus).toHaveBeenCalledTimes(1));
    expect(
      screen.getByRole('button', { name: 'listVisibility.hideFile' }),
    ).toBeInTheDocument();
  },
);

it('preserves visibility on a network failure', async () => {
  mockSetStatus.mockRejectedValue(new Error('offline'));
  renderFile();
  fireEvent.click(screen.getByTestId('document-toggle-visibility'));
  await waitFor(() => expect(mockSetStatus).toHaveBeenCalledTimes(1));
  expect(
    screen.getByRole('button', { name: 'listVisibility.hideFile' }),
  ).toBeInTheDocument();
});
