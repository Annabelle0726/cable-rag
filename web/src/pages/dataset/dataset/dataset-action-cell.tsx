import { ConfirmDeleteDialog } from '@/components/confirm-delete-dialog';
import { Button } from '@/components/ui/button';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { DocumentType } from '@/constants/knowledge';
import { UseRowSelectionType } from '@/hooks/logic-hooks/use-row-selection';
import { useCanManageDataset } from '@/hooks/use-can-manage-dataset';
import { useKnowledgeBaseContext } from '../contexts/knowledge-base-context';
import { useTranslation } from 'react-i18next';
import {
  useSetDocumentStatus,
  useRemoveDocument,
} from '@/hooks/use-document-request';
import { IDocumentInfo } from '@/interfaces/database/document';
import { downloadDatasetDocument } from '@/services/file-manager-service';
import { formatFileSize } from '@/utils/common-util';
import { formatDate } from '@/utils/date';
import { downloadFileFromBlob } from '@/utils/file-util';
import { Download, Eye, EyeOff, PenLine, Trash2 } from 'lucide-react';
import { omit } from 'lodash';
import { useCallback } from 'react';
import { UseRenameDocumentShowType } from './use-rename-document';
import { isDocumentProcessing } from './utils';

const Fields = ['name', 'size', 'type', 'create_time', 'update_time'];

const FunctionMap = {
  size: formatFileSize,
  create_time: formatDate,
  update_time: formatDate,
};

export function DatasetActionCell({
  record,
  showRenameModal,
  setRowSelection,
}: { record: IDocumentInfo } & UseRenameDocumentShowType &
  Pick<UseRowSelectionType, 'setRowSelection'>) {
  const { t } = useTranslation();
  const { knowledgeBase } = useKnowledgeBaseContext();
  const canManage = useCanManageDataset(knowledgeBase);
  const { setDocumentStatus, loading: visibilityLoading } =
    useSetDocumentStatus();
  const hidden = record.status === '0';
  const visibilityLabel = t(
    hidden ? 'listVisibility.restoreFile' : 'listVisibility.hideFile',
  );
  const handleToggleVisibility = useCallback(async () => {
    if (!canManage) return;
    try {
      await setDocumentStatus({
        documentId: record.id,
        datasetId: record.dataset_id,
        status: hidden,
      });
    } catch {
      // The request layer reports errors; retain the server-provided state.
    }
  }, [canManage, hidden, record.id, record.dataset_id, setDocumentStatus]);
  const { id, type } = record;
  const isRunning = isDocumentProcessing(record);
  const isVirtualDocument = type === DocumentType.Virtual;

  const { removeDocument } = useRemoveDocument();

  const onDownloadDocument = useCallback(async () => {
    try {
      const ext = record.name.split('.').pop()?.toLowerCase() || 'bin';
      const response = await downloadDatasetDocument({
        datasetId: record.dataset_id,
        docId: id,
        ext,
      });
      const blob = new Blob([response.data], {
        type: response.data.type,
      });
      downloadFileFromBlob(blob, record.name);
    } catch (error) {
      console.error('Error downloading document:', error);
    }
  }, [id, record.dataset_id, record.name]);

  const handleRemove = useCallback(async () => {
    const code = await removeDocument(id);
    if (code === 0) {
      setRowSelection((prev) => omit(prev, [id]));
    }
  }, [id, removeDocument, setRowSelection]);

  const handleRename = useCallback(() => {
    showRenameModal(record);
  }, [record, showRenameModal]);

  return (
    <div className="flex gap-2 items-center">
      <Button
        size="icon-xs"
        variant="ghost"
        disabled={isRunning}
        onClick={handleRename}
      >
        <PenLine className="size-[1em]" />
      </Button>
      <HoverCard>
        <HoverCardTrigger>
          <Button size="icon-xs" variant="ghost" disabled={isRunning}>
            <Eye className="size-[1em]" />
          </Button>
        </HoverCardTrigger>
        <HoverCardContent className="w-[40vw] max-h-[40vh] overflow-auto">
          <ul className="space-y-2">
            {Object.entries(record)
              .filter(([key]) => Fields.some((x) => x === key))

              .map(([key, value], idx) => {
                return (
                  <li key={idx} className="flex gap-2">
                    {key}:
                    <div>
                      {key in FunctionMap
                        ? FunctionMap[key as keyof typeof FunctionMap](value)
                        : value}
                    </div>
                  </li>
                );
              })}
          </ul>
        </HoverCardContent>
      </HoverCard>

      {isVirtualDocument || (
        <Button
          size="icon-xs"
          variant="ghost"
          onClick={onDownloadDocument}
          disabled={isRunning}
        >
          <Download className="size-[1em]" />
        </Button>
      )}
      <Button
        size="icon-xs"
        variant="ghost"
        disabled={!canManage || isRunning || visibilityLoading}
        onClick={handleToggleVisibility}
        aria-label={visibilityLabel}
        title={visibilityLabel}
        data-testid="document-toggle-visibility"
      >
        {hidden ? (
          <Eye className="size-[1em]" />
        ) : (
          <EyeOff className="size-[1em]" />
        )}
      </Button>
      <ConfirmDeleteDialog onOk={handleRemove}>
        <Button
          data-testid="document-delete"
          size="icon-xs"
          variant="ghost"
          disabled={isRunning}
        >
          <Trash2 className="size-[1em]" />
        </Button>
      </ConfirmDeleteDialog>
    </div>
  );
}
