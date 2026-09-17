import {
  DatasetCategoryChip,
  DatasetCategoryIcon,
} from '@/components/dataset-category';
import { HomeCard } from '@/components/home-card';
import { MoreButton } from '@/components/more-button';
import { SharedBadge } from '@/components/shared-badge';
import { Card, CardContent } from '@/components/ui/card';
import { resolveDatasetCategory } from '@/constants/dataset-category';
import { useNavigatePage } from '@/hooks/logic-hooks/navigate-hooks';
import { IDataset } from '@/interfaces/database/dataset';
import { t } from 'i18next';
import { ChevronRight } from 'lucide-react';
import { DatasetDropdown } from './dataset-dropdown';
import { useRenameDataset } from './use-rename-dataset';

export type DatasetCardProps = {
  dataset: IDataset;
} & Pick<ReturnType<typeof useRenameDataset>, 'showDatasetRenameModal'>;

export function DatasetCard({
  dataset,
  showDatasetRenameModal,
}: DatasetCardProps) {
  const { navigateToDataset } = useNavigatePage();
  const { category } = resolveDatasetCategory(dataset);

  return (
    <HomeCard
      data={{
        ...dataset,
        description: `${dataset.document_count} ${t('knowledgeDetails.files')}`,
      }}
      // An uploaded avatar is the owner's own branding and stays; the
      // first-letter placeholder it falls back to is replaced by the class icon,
      // which says something about the knowledge base instead of repeating the
      // first character of its name.
      leading={
        dataset.avatar ? undefined : <DatasetCategoryIcon category={category} />
      }
      badge={<DatasetCategoryChip dataset={dataset} />}
      moreDropdown={
        <DatasetDropdown
          showDatasetRenameModal={showDatasetRenameModal}
          dataset={dataset}
        >
          <MoreButton></MoreButton>
        </DatasetDropdown>
      }
      sharedBadge={<SharedBadge>{dataset.nickname}</SharedBadge>}
      onClick={navigateToDataset(dataset.id)}
    />
  );
}

export function SeeAllCard() {
  const { navigateToDatasetList } = useNavigatePage();

  return (
    <Card
      className="card-interactive w-full flex-none h-full border border-ceramic-border bg-glass shadow-ceramic hover:border-ceramic-border-hover hover:shadow-ceramic-hover transition-[background-color,border-color,box-shadow,opacity] duration-200 ease-in-out"
      onClick={() => navigateToDatasetList({ isCreate: false })}
    >
      <CardContent className="p-2.5 pt-1 w-full h-full flex items-center justify-center gap-1.5 text-text-secondary">
        {t('common.seeAll')} <ChevronRight className="size-4" />
      </CardContent>
    </Card>
  );
}
