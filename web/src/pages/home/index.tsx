import { PageContainer, PageContent } from '@/layouts/components/page-container';
import { AppFooter } from '@/layouts/components/app-footer';
import { Applications } from './applications';
import { Datasets } from './datasets';

const Home = () => {
  return (
    <PageContainer className="pt-4 pb-0">
      <PageContent>
        {/* The 查询条件 panel at the head of the knowledge-base section is the
            page's first element, so the operator lands on the search form and the
            data table it drives instead of a marketing banner. */}
        <article className="pb-6">
          <Datasets />
          <Applications />
        </article>
      </PageContent>

      <AppFooter />
    </PageContainer>
  );
};

export default Home;
