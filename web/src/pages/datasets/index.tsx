import { CardContainer } from '@/components/card-container';
import { EmptyCardType } from '@/components/empty/constant';
import { EmptyAppCard } from '@/components/empty/empty';
import ListFilterBar from '@/components/list-filter-bar';
import { RenameDialog } from '@/components/rename-dialog';
import { Button } from '@/components/ui/button';
import { RAGFlowPagination } from '@/components/ui/ragflow-pagination';
import { Spin } from '@/components/ui/spin';
import { ListDeletionKey } from '@/constants/list-deletion';
import { useGoToPreviousPageOnEmpty } from '@/hooks/logic-hooks';
import { useFetchNextKnowledgeListByPage } from '@/hooks/use-knowledge-request';
import { useQueryClient } from '@tanstack/react-query';
import { pick } from 'lodash';
import { Plus } from 'lucide-react';
import { useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import { DatasetCard } from './dataset-card';
import { DatasetCreatingDialog } from './dataset-creating-dialog';
import { useSaveKnowledge } from './hooks';
import { useRenameDataset } from './use-rename-dataset';
import { useSelectOwners } from './use-select-owners';

export default function Datasets() {
  const { t } = useTranslation();
  const {
    visible,
    hideModal,
    showModal,
    onCreateOk,
    loading: creatingLoading,
  } = useSaveKnowledge();

  const {
    kbs,
    total_datasets,
    pagination,
    setPagination,
    handleInputChange,
    searchString,
    setSearchString,
    filterValue,
    setFilterValue,
    handleFilterSubmit,
    loading,
  } = useFetchNextKnowledgeListByPage();

  const owners = useSelectOwners();

  const {
    datasetRenameLoading,
    initialDatasetName,
    onDatasetRenameOk,
    datasetRenameVisible,
    hideDatasetRenameModal,
    showDatasetRenameModal,
  } = useRenameDataset();

  const handlePageChange = useCallback(
    (page: number, pageSize?: number) => {
      setPagination({ page, pageSize });
    },
    [setPagination],
  );
  useGoToPreviousPageOnEmpty(kbs?.length, loading, {
    deletionKey: ListDeletionKey.KnowledgeList,
    searchString,
    setSearchString,
    filterValue,
    setFilterValue,
  });
  const [searchUrl, setSearchUrl] = useSearchParams();
  const isCreate = searchUrl.get('isCreate') === 'true';
  const queryClient = useQueryClient();
  useEffect(() => {
    if (isCreate) {
      queryClient.invalidateQueries({ queryKey: ['tenantInfo'] });
      showModal();
      searchUrl.delete('isCreate');
      setSearchUrl(searchUrl);
    }
  }, [isCreate, showModal, searchUrl, setSearchUrl, queryClient]);

  return (
    <>
      {loading && !kbs?.length ? (
        <article
          className="size-full flex items-center justify-center"
          data-testid="datasets-list"
        >
          <Spin size="large" />
        </article>
      ) : kbs?.length || searchString ? (
        <article
          className="size-full min-w-0 flex flex-col"
          data-testid="datasets-list"
        >
          <header className="page-gutter mb-4 min-w-0 pt-8">
            <ListFilterBar
              searchVariant="capsule"
              title={t('header.dataset')}
              searchString={searchString}
              onSearchChange={handleInputChange}
              value={filterValue}
              filters={owners}
              onChange={handleFilterSubmit}
              icon={'datasets'}
            >
              <Button
                className="ceramic-cta h-10 rounded-full px-5"
                onClick={showModal}
              >
                <Plus className="size-[1em]" />
                {t('knowledgeList.createKnowledgeBase')}
              </Button>
            </ListFilterBar>
          </header>

          {kbs?.length ? (
            <>
              <CardContainer className="page-gutter flex-1 overflow-auto">
                {kbs.map((dataset) => (
                  <DatasetCard
                    dataset={dataset}
                    key={dataset.id}
                    showDatasetRenameModal={showDatasetRenameModal}
                  />
                ))}
              </CardContainer>

              <footer className="page-gutter mt-4 pb-5">
                <RAGFlowPagination
                  {...pick(pagination, 'current', 'pageSize')}
                  total={total_datasets}
                  onChange={handlePageChange}
                />
              </footer>
            </>
          ) : (
            // The create tile is a grid item in the same container the cards use,
            // so it is exactly as wide and as tall as a knowledge-base card.
            <CardContainer className="page-gutter flex-1 overflow-auto">
              <EmptyAppCard
                showIcon
                isSearch
                type={EmptyCardType.Dataset}
                onClick={() => showModal()}
              />
            </CardContainer>
          )}
        </article>
      ) : (
        <article
          className="size-full min-w-0 flex flex-col"
          data-testid="datasets-list"
        >
          <CardContainer className="page-gutter flex-1 overflow-auto pt-8">
            <EmptyAppCard
              showIcon
              type={EmptyCardType.Dataset}
              onClick={() => showModal()}
            />
          </CardContainer>
        </article>
      )}
      {visible && (
        <DatasetCreatingDialog
          hideModal={hideModal}
          onOk={onCreateOk}
          loading={creatingLoading}
        ></DatasetCreatingDialog>
      )}
      {datasetRenameVisible && (
        <RenameDialog
          hideModal={hideDatasetRenameModal}
          onOk={onDatasetRenameOk}
          initialName={initialDatasetName}
          loading={datasetRenameLoading}
        ></RenameDialog>
      )}
    </>
  );
}
