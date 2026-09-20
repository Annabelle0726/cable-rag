import { Outlet } from 'react-router';
import { BreadcrumbBar } from './components/breadcrumb-bar';
import { BreadcrumbTrailProvider } from './components/breadcrumb-context';
import { Header } from './components/header';

export function RootLayoutContainer({ children }: React.PropsWithChildren) {
  return (
    // The trail provider wraps the bar and the page together, so a page below can
    // publish the entity levels the bar renders above it.
    <BreadcrumbTrailProvider>
      <div className="size-full min-w-0 grid grid-flow-col grid-cols-1 grid-rows-[auto_auto_1fr] bg-cable-page">
        {/* The 国网 bar spans the window as one solid green block and the header
            inside it keeps its own max-width gutter: putting the gutter on the bar
            itself stopped the green at 1280px and left the page canvas bare on
            either side, which is the seam that made the bar look pasted on. */}
        <div className="glass-header">
          <Header />
        </div>

        <BreadcrumbBar />

        {/* No footer row here: the 政企 footer belongs to the page that wants one
            (see `pages/home`), so it does not repeat under every route. */}
        <main className="size-full min-w-0 overflow-hidden">{children}</main>
      </div>
    </BreadcrumbTrailProvider>
  );
}

export default function RootLayout() {
  return (
    <RootLayoutContainer>
      <Outlet />
    </RootLayoutContainer>
  );
}
