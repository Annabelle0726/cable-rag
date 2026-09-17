import { PageContainer, PageContent } from '@/layouts/components/page-container';
import { Applications } from './applications';
import { NextBanner } from './banner';
import { Datasets } from './datasets';

const Home = () => {
  return (
    <PageContainer>
      <PageContent>
        {/* The page container already ends the scroll area with its own bottom
            padding, and every card grid ends with a 24px filler, so this only has
            to top those up: 64px here read as an empty screen below the last row. */}
        <article className="pb-6">
          <header>
            <NextBanner />
          </header>

          <Datasets />
          <Applications />
        </article>
      </PageContent>
    </PageContainer>
  );
};

export default Home;
