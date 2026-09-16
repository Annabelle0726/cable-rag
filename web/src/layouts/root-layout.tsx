import { Outlet } from 'react-router';
import { Header } from './components/header';

export function RootLayoutContainer({ children }: React.PropsWithChildren) {
  return (
    <div className="size-full min-w-0 grid grid-flow-col grid-cols-1 grid-rows-[auto_1fr] bg-cable-page">
      {/* The glass bar spans the window and the header inside it keeps its own
          max-width gutter: putting the gutter on the bar itself stopped the
          glass at 1280px and left the page canvas bare on either side, which is
          the seam that made the bar look pasted on. */}
      <div className="glass-header">
        <Header />
      </div>

      <main className="size-full min-w-0 overflow-hidden">{children}</main>
    </div>
  );
}

export default function RootLayout() {
  return (
    <RootLayoutContainer>
      <Outlet />
    </RootLayoutContainer>
  );
}
