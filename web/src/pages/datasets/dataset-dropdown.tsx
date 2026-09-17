import {
  ConfirmDeleteDialog,
  ConfirmDeleteDialogNode,
} from '@/components/confirm-delete-dialog';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  DatasetCategory,
  DatasetCategoryDefinitions,
  DatasetCategoryNavOrder,
  resolveDatasetCategory,
} from '@/constants/dataset-category';
import { useDeleteKnowledge, useUpdateKnowledge } from '@/hooks/use-knowledge-request';
import { IDataset } from '@/interfaces/database/dataset';
import { LucideTags, PenLine, RotateCcw, Trash2 } from 'lucide-react';
import { MouseEventHandler, PropsWithChildren, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useRenameDataset } from './use-rename-dataset';

export function DatasetDropdown({
  children,
  showDatasetRenameModal,
  dataset,
}: PropsWithChildren &
  Pick<ReturnType<typeof useRenameDataset>, 'showDatasetRenameModal'> & {
    dataset: IDataset;
  }) {
  const { t } = useTranslation();
  const { deleteKnowledge } = useDeleteKnowledge();
  // The class is stored on the dataset itself, so every user and every browser
  // sees the same filing; `true` refreshes the paginated list the cards read.
  const { saveKnowledgeConfiguration } = useUpdateKnowledge(true);

  const { category: resolvedCategory, customTag } = resolveDatasetCategory(dataset);

  const handleShowDatasetRenameModal: MouseEventHandler<HTMLDivElement> =
    useCallback(
      (e) => {
        e.stopPropagation();
        showDatasetRenameModal(dataset);
      },
      [dataset, showDatasetRenameModal],
    );

  const handleDelete: MouseEventHandler<HTMLDivElement> = useCallback(() => {
    deleteKnowledge(dataset.id);
  }, [dataset.id, deleteKnowledge]);

  // The menu lives in a portal but React still bubbles its clicks up the React
  // tree to the card, which would navigate away.
  const handleStopPropagation: MouseEventHandler<HTMLDivElement> = useCallback(
    (e) => {
      e.stopPropagation();
    },
    [],
  );

  const handleMoveToCategory = useCallback(
    (category: DatasetCategory) => {
      saveKnowledgeConfiguration({ kb_id: dataset.id, category });
    },
    [dataset.id, saveKnowledgeConfiguration],
  );

  const handleUseAutomaticCategory = useCallback(() => {
    // An empty class means "nobody chose one", so the card falls back to the
    // class its name implies.
    saveKnowledgeConfiguration({ kb_id: dataset.id, category: '' });
  }, [dataset.id, saveKnowledgeConfiguration]);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem onClick={handleShowDatasetRenameModal}>
          {t('common.rename')} <PenLine />
        </DropdownMenuItem>
        <DropdownMenuSeparator />

        <DropdownMenuSub>
          <DropdownMenuSubTrigger
            onClick={handleStopPropagation}
            data-testid="dataset-category-menu"
          >
            <LucideTags className="size-4" />
            {t('datasetCategory.moveTo')}
          </DropdownMenuSubTrigger>

          <DropdownMenuSubContent className="w-56">
            {DatasetCategoryNavOrder.map((category) => {
              const { icon: CategoryIcon, labelKey, toneClass } =
                DatasetCategoryDefinitions[category];

              return (
                <DropdownMenuCheckboxItem
                  key={category}
                  checked={!customTag && resolvedCategory === category}
                  onClick={handleStopPropagation}
                  onCheckedChange={() => handleMoveToCategory(category)}
                  data-testid={`dataset-category-set-${category}`}
                  className={toneClass}
                >
                  <CategoryIcon className="category-ink size-4" aria-hidden />
                  {t(labelKey)}
                </DropdownMenuCheckboxItem>
              );
            })}

            <DropdownMenuSeparator />
            <DropdownMenuCheckboxItem
              checked={!dataset.category}
              onClick={handleStopPropagation}
              onCheckedChange={handleUseAutomaticCategory}
              data-testid="dataset-category-set-auto"
            >
              <RotateCcw className="size-4" />
              {t('datasetCategory.auto')}
            </DropdownMenuCheckboxItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>

        <DropdownMenuSeparator />
        <ConfirmDeleteDialog
          onOk={handleDelete}
          title={t('deleteModal.delDataset')}
          content={{
            node: (
              <ConfirmDeleteDialogNode
                avatar={{ avatar: dataset.avatar, name: dataset.name }}
                name={dataset.name}
              />
            ),
          }}
        >
          <DropdownMenuItem
            className="text-state-error"
            onSelect={(e) => {
              e.preventDefault();
            }}
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            {t('common.delete')} <Trash2 />
          </DropdownMenuItem>
        </ConfirmDeleteDialog>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
