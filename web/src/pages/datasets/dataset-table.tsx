import { DatasetCategoryChip } from '@/components/dataset-category';
import { MoreButton } from '@/components/more-button';
import { SharedBadge } from '@/components/shared-badge';
import { TableSkeleton } from '@/components/table-skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useNavigatePage } from '@/hooks/logic-hooks/navigate-hooks';
import { IDataset } from '@/interfaces/database/dataset';
import { cn } from '@/lib/utils';
import { formatDate } from '@/utils/date';
import { useTranslation } from 'react-i18next';
import { DatasetDropdown } from './dataset-dropdown';
import { useRenameDataset } from './use-rename-dataset';

/** `'1'` is an enabled knowledge base; anything else is filed away. */
const isAvailable = (dataset: IDataset) => dataset.status === '1';

/** Column widths: the identity and status columns are fixed, the name and the
 *  timestamp take the slack so a long name truncates instead of pushing 操作 off
 *  the row. */
const ColumnWidth = {
  identity: 'w-[136px]',
  documentCount: 'w-[120px]',
  updateTime: 'w-[196px]',
  status: 'w-[104px]',
  operation: 'w-[168px]',
} as const;

/** 表头单元格：40px 高、#F5F7FA 底、#303133 半粗体（见 tailwind.css 的 --table-head-ink）。 */
const headCellClass = 'h-10 text-[13px] font-semibold text-table-head-ink';

export type DatasetTableProps = {
  datasets: IDataset[];
  loading?: boolean;
  className?: string;
} & Pick<ReturnType<typeof useRenameDataset>, 'showDatasetRenameModal'>;

/**
 * 国网 ECP 风格知识库数据表。
 *
 * 卡片改为高密度表格：表头 #F5F7FA / 40px，行高 38px，每行一条 1px 浅灰下边框，
 * Hover 整行转为 #F5F7FA 灰底。列序固定为「标识 / 数据集名称 / 文件数量 /
 * 最后更新时间 / 状态 / 操作」。
 */
export function DatasetTable({
  datasets,
  loading = false,
  className,
  showDatasetRenameModal,
}: DatasetTableProps) {
  const { t } = useTranslation();
  const { navigateToDataset } = useNavigatePage();

  return (
    <Table
      className="min-w-[920px] text-sm"
      rootClassName={cn(
        'border border-panel-border bg-bg-component',
        className,
      )}
      data-testid="dataset-table"
    >
      <TableHeader className="bg-table-header">
        <TableRow className="hover:bg-table-header">
          {/* One header spec for every column: #303133 半粗体 on #F5F7FA, 40px 高。 */}
          <TableHead className={cn(headCellClass, ColumnWidth.identity)}>
            {t('datasetTable.identity')}
          </TableHead>
          <TableHead className={headCellClass}>
            {t('datasetTable.name')}
          </TableHead>
          <TableHead className={cn(headCellClass, ColumnWidth.documentCount)}>
            {t('datasetTable.documentCount')}
          </TableHead>
          <TableHead className={cn(headCellClass, ColumnWidth.updateTime)}>
            {t('datasetTable.updateTime')}
          </TableHead>
          <TableHead className={cn(headCellClass, ColumnWidth.status)}>
            {t('datasetTable.status')}
          </TableHead>
          <TableHead className={cn(headCellClass, ColumnWidth.operation)}>
            {t('datasetTable.operation')}
          </TableHead>
        </TableRow>
      </TableHeader>

      <TableBody>
        {loading ? (
          <TableSkeleton columnsLength={6} />
        ) : datasets.length ? (
          datasets.map((dataset) => (
            <TableRow
              key={dataset.id}
              className="h-[38px] border-b border-table-border hover:bg-table-row-hover"
              data-testid="dataset-row"
            >
              <TableCell className="h-[38px] py-0 align-middle">
                <DatasetCategoryChip dataset={dataset} className="px-1.5" />
              </TableCell>

              <TableCell className="h-[38px] min-w-0 py-0 align-middle">
                <div className="flex min-w-0 items-center gap-2">
                  <button
                    type="button"
                    onClick={navigateToDataset(dataset.id)}
                    title={dataset.name}
                    className="min-w-0 truncate text-left text-text-primary transition-colors hover:text-cable-brand hover:underline"
                    data-testid="dataset-name"
                  >
                    {dataset.name}
                  </button>
                  <span className="shrink-0">
                    <SharedBadge>{dataset.nickname}</SharedBadge>
                  </span>
                </div>
              </TableCell>

              <TableCell className="h-[38px] py-0 align-middle text-content-secondary">
                {t('datasetTable.files', { value: dataset.document_count })}
              </TableCell>

              <TableCell className="h-[38px] py-0 align-middle tabular-nums text-content-secondary">
                {formatDate(dataset.update_time, 'YYYY-MM-DD HH:mm:ss')}
              </TableCell>

              <TableCell className="h-[38px] py-0 align-middle">
                <span
                  className={cn(
                    'inline-flex items-center border px-1.5 py-0.5 text-xs leading-none',
                    isAvailable(dataset)
                      ? 'border-status-available-border bg-status-available text-status-available-ink'
                      : 'border-status-archived-border bg-status-archived text-status-archived-ink',
                  )}
                  data-testid="dataset-status"
                >
                  {t(
                    isAvailable(dataset)
                      ? 'datasetTable.available'
                      : 'datasetTable.archived',
                  )}
                </span>
              </TableCell>

              <TableCell className="h-[38px] py-0 align-middle">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={navigateToDataset(dataset.id)}
                    className="text-cable-brand transition-colors hover:text-accent-color-strong hover:underline"
                    data-testid="dataset-view-details"
                  >
                    {t('datasetTable.viewDetails')}
                  </button>

                  {/* Rename / reclassify / delete live in the shared menu, so a
                      row and a card offer exactly the same actions. */}
                  <DatasetDropdown
                    dataset={dataset}
                    showDatasetRenameModal={showDatasetRenameModal}
                  >
                    <MoreButton className="size-4 opacity-100" />
                  </DatasetDropdown>
                </div>
              </TableCell>
            </TableRow>
          ))
        ) : (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={6}
              className="h-[120px] text-center align-middle text-content-tertiary"
            >
              {t('datasetTable.empty')}
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
