import { EmptyCardType } from '@/components/empty/constant';
import { EmptyAppCard } from '@/components/empty/empty';
import { FilterButton } from '@/components/list-filter-bar';
import { FilterPopover } from '@/components/list-filter-bar/filter-popover';
import { RenameDialog } from '@/components/rename-dialog';
import { Button } from '@/components/ui/button';
import { RAGFlowPagination } from '@/components/ui/ragflow-pagination';
import { ListDeletionKey } from '@/constants/list-deletion';
import { useGoToPreviousPageOnEmpty } from '@/hooks/logic-hooks';
import { useFetchNextKnowledgeListByPage } from '@/hooks/use-knowledge-request';
import { useQueryClient } from '@tanstack/react-query';
import { pick } from 'lodash';
import { Plus } from 'lucide-react';
import { useCallback, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import { DatasetTable } from './dataset-table';
import { DatasetCreatingDialog } from './dataset-creating-dialog';
import { useSaveKnowledge } from './hooks';
import { DatasetQueryPanel } from './query-panel';
import { useDatasetQuery } from './use-dataset-query';
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

  const {
    query,
    setCategory,
    setKeyword,
    setCreatedFrom,
    setCreatedTo,
    reset,
    filter,
  } = useDatasetQuery();

  const datasets = useMemo(() => filter(kbs ?? []), [filter, kbs]);

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

  const handleKeywordChange = useCallback(
    (keyword: string) => {
      setKeyword(keyword);
      // The panel's keyword and the list's own search box are one control: the
      // panel narrows what is on screen, the debounced request behind
      // `setSearchString` widens the page to every match on the server.
      setSearchString(keyword);
    },
    [setKeyword, setSearchString],
  );

  const handleReset = useCallback(() => {
    reset();
    setSearchString('');
  }, [reset, setSearchString]);

  /** Owner stays a popover filter: it is a tenant-scoped multi-select, not one of
   *  the panel's three single-value conditions. */
  const ownerFilterCount = useMemo(
    () => (Array.isArray(filterValue?.owner) ? filterValue.owner.length : 0),
    [filterValue],
  );

  if (loading && !kbs?.length) {
    return (
      <article className="page-gutter py-4" data-testid="datasets-list">
        <DatasetTable
          datasets={[]}
          loading
          showDatasetRenameModal={showDatasetRenameModal}
        />
      </article>
    );
  }

  return (
    <article
      className="flex size-full min-w-0 flex-col overflow-auto"
      data-testid="datasets-list"
    >
      <header className="page-gutter flex min-w-0 items-center justify-between gap-4 py-3">
        <h1 className="truncate text-base font-semibold text-text-primary">
          {t('header.dataset')}
        </h1>
        <div className="flex shrink-0 items-center gap-2">
          <FilterPopover
            value={filterValue}
            onChange={handleFilterSubmit}
            filters={owners}
          >
            <FilterButton count={ownerFilterCount} />
          </FilterPopover>

          <Button
            className="ceramic-cta h-8 shrink-0 rounded-[2px] px-3 text-xs font-medium gap-1.5"
            onClick={showModal}
          >
            <Plus className="size-3.5" />
            {t('knowledgeList.createKnowledgeBase')}
          </Button>
        </div>
      </header>

      <DatasetQueryPanel
        className="page-gutter mb-3 border-x-0 border-t-0"
        query={query}
        onCategoryChange={setCategory}
        onKeywordChange={handleKeywordChange}
        onCreatedFromChange={setCreatedFrom}
        onCreatedToChange={setCreatedTo}
        onReset={handleReset}
      />

      {kbs?.length || searchString ? (
        <>
          <div className="page-gutter min-h-0 flex-1 overflow-auto">
            <DatasetTable
              datasets={datasets}
              loading={loading}
              showDatasetRenameModal={showDatasetRenameModal}
            />
          </div>

          <footer className="page-gutter py-3">
            <RAGFlowPagination
              {...pick(pagination, 'current', 'pageSize')}
              total={total_datasets}
              onChange={handlePageChange}
            />
          </footer>
        </>
      ) : (
        <div className="page-gutter pb-6">
          <EmptyAppCard
            showIcon
            type={EmptyCardType.Dataset}
            onClick={() => showModal()}
          />
        </div>
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
    </article>
  );
}
