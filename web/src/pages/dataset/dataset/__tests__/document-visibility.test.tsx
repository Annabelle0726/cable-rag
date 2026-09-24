import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { DatasetActionCell } from '../dataset-action-cell';
const ActionCell = DatasetActionCell;
type DocumentRecord = Parameters<typeof ActionCell>[0]['record'];

jest.mock('@/components/confirm-delete-dialog', () => ({
  ConfirmDeleteDialog: ({ children }: { children: React.ReactNode }) =>
    children,
}));
const mockSetStatus = jest.fn();
let mockCanManage = true;
let mockParentHidden = false;
jest.mock('@/hooks/use-dataset-preferences', () => ({
  useDatasetPreferences: () => ({ isHidden: () => mockParentHidden }),
}));
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
  useKnowledgeBaseContext: () => ({ knowledgeBase: { id: 'kb-1' } }),
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
    <TooltipProvider delayDuration={0}>
      <DatasetActionCell
        record={record}
        showRenameModal={jest.fn()}
        setRowSelection={jest.fn()}
      />
    </TooltipProvider>,
  );
}

beforeEach(() => {
  mockParentHidden = false;
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

it('uses distinct detail and state icons with labels on all five actions', () => {
  const { container } = renderFile();
  expect(
    screen
      .getByRole('button', { name: 'listVisibility.fileDetails' })
      .querySelector('.lucide-info'),
  ).not.toBeNull();
  expect(
    screen
      .getByTestId('document-toggle-visibility')
      .querySelector('.lucide-eye'),
  ).not.toBeNull();
  expect(container.querySelectorAll('button[aria-label]')).toHaveLength(5);
});

it('shows the crossed-out eye for hidden files', () => {
  renderFile('0');
  expect(
    screen
      .getByTestId('document-toggle-visibility')
      .querySelector('.lucide-eye-off'),
  ).not.toBeNull();
});

it('opens file details by click', async () => {
  renderFile();
  fireEvent.click(
    screen.getByRole('button', { name: 'listVisibility.fileDetails' }),
  );
  expect(await screen.findByText('file.pdf')).toBeInTheDocument();
});

it.each([
  'common.edit',
  'listVisibility.fileDetails',
  'common.download',
  'listVisibility.hideFile',
  'common.delete',
])('shows a tooltip for %s', async (label) => {
  renderFile();
  fireEvent.focus(screen.getByRole('button', { name: label }).parentElement!);
  expect(await screen.findByRole('tooltip')).toHaveTextContent(label);
});

it.each(['0', '1'])(
  'inherits parent hiding without changing stored status %s',
  (status) => {
    mockParentHidden = true;
    renderFile(status);
    const button = screen.getByTestId('document-toggle-visibility');
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute(
      'aria-label',
      'listVisibility.inheritedHidden',
    );
    expect(button.querySelector('.lucide-eye-off')).not.toBeNull();
    fireEvent.click(button);
    expect(mockSetStatus).not.toHaveBeenCalled();
  },
);
