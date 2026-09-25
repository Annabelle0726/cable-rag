import { useFetchKnowledgeBaseConfiguration } from '@/hooks/use-knowledge-request';
import { usePublishBreadcrumbTrail } from '@/layouts/components/breadcrumb-context';
import { KnowledgeBaseProvider } from '@/pages/dataset/contexts/knowledge-base-context';
import { Routes } from '@/routes';
import { useMemo } from 'react';

import { Outlet, useParams } from 'react-router';
import { SideBar } from './sidebar';

export default function DatasetWrapper() {
  const { data, loading } = useFetchKnowledgeBaseConfiguration();
  const { id } = useParams();

  // The knowledge base's name is the second level of the global breadcrumb, and
  // the page that fetches it is the only place that already holds it: the bar sits
  // above this route and cannot reach `KnowledgeBaseProvider`. The link points at
  // the files view — this knowledge base's main view — so the level is a real
  // parent rather than the bare `/dataset` shell, which renders nothing on its own.
  const trail = useMemo(
    () =>
      data?.name && id
        ? [
            {
              label: data.name,
              to: `${Routes.DatasetBase}${Routes.Files}/${id}`,
            },
          ]
        : [],
    [data?.name, id],
  );

  usePublishBreadcrumbTrail(trail);

  return (
    <KnowledgeBaseProvider knowledgeBase={data} loading={loading}>
      <article className="pt-3 size-full grid grid-cols-[auto_minmax(0,1fr)] grid-rows-1">
        <SideBar dataset={data} />

        <div className="min-w-0 min-h-0 overflow-auto">
          <Outlet />
        </div>
      </article>
    </KnowledgeBaseProvider>
  );
}
