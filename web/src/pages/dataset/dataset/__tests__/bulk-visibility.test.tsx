import { renderHook } from '@testing-library/react';
import { useBulkOperateDataset } from '../use-bulk-operate-dataset';
let mockParentHidden = false;
const mockSetStatus = jest.fn();
jest.mock('../use-document-visibility', () => ({
  useDocumentVisibility: () => ({ parentHidden: mockParentHidden }),
}));
jest.mock('@/hooks/use-document-request', () => ({
  useRunDocument: () => ({ runDocumentByIds: jest.fn() }),
  useSetDocumentStatus: () => ({ setDocumentStatus: mockSetStatus }),
  useRemoveDocument: () => ({ removeDocument: jest.fn() }),
}));
jest.mock('@/hooks/common-hooks', () => ({
  useSetModalState: () => ({
    visible: false,
    showModal: jest.fn(),
    hideModal: jest.fn(),
  }),
}));
jest.mock('@/hooks/logic-hooks/use-row-selection', () => ({
  useSelectedIds: () => ({ selectedIds: ['doc-1'] }),
}));
jest.mock('../use-parser-gap-validation', () => ({
  useParserGapValidation: () => ({ findDocumentParseGaps: jest.fn() }),
}));
jest.mock('../parser-gap-content', () => ({
  buildParserGapModalContent: jest.fn(),
}));
jest.mock('../utils', () => ({ isDocumentProcessing: () => false }));
jest.mock('../../contexts/knowledge-base-context', () => ({
  useKnowledgeBaseContext: () => ({ knowledgeBase: { id: 'kb-1' } }),
}));
jest.mock('react-router', () => ({ useParams: () => ({ id: 'kb-1' }) }));
jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

it('suppresses bulk visibility controls while the parent dataset is hidden', () => {
  mockParentHidden = true;
  const { result, rerender } = renderHook(() =>
    useBulkOperateDataset({
      rowSelection: {},
      setRowSelection: jest.fn(),
      documents: [],
    }),
  );
  expect(result.current.list.map((item) => item.id)).not.toContain('enabled');
  expect(result.current.list.map((item) => item.id)).not.toContain('disabled');
  expect(mockSetStatus).not.toHaveBeenCalled();
  mockParentHidden = false;
  rerender();
  expect(result.current.list.map((item) => item.id)).toEqual(
    expect.arrayContaining(['enabled', 'disabled']),
  );
});
