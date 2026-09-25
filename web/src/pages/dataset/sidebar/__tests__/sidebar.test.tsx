import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { TooltipProvider } from '@/components/ui/tooltip';
import { SideBar } from '..';

const SidebarComponent = SideBar;
jest.mock('@/routes', () => ({
  Routes: {
    DatasetBase: '/dataset',
    Files: '/files',
    DatasetTesting: '/testing',
    DataSetOverview: '/overview',
    DataSetSetting: '/setting',
    Compilation: '/compilation',
  },
}));
jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock('@/hooks/route-hook', () => ({ useSecondPathName: () => 'files' }));
jest.mock('@/components/dataset-category', () => ({
  DatasetIdentityMark: () => <span>identity</span>,
}));

const renderSidebar = () =>
  render(
    <MemoryRouter>
      <TooltipProvider delayDuration={0}>
        <SidebarComponent
          dataset={
            { name: 'Test dataset', create_time: 0 } as Parameters<
              typeof SidebarComponent
            >[0]['dataset']
          }
        />
      </TooltipProvider>
    </MemoryRouter>,
  );

beforeEach(() => localStorage.clear());

it('collapses to accessible navigation icons, remembers the state and expands again', async () => {
  const first = renderSidebar();
  expect(screen.getByText('Test dataset')).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('button', { name: 'knowledgeDetails.collapseSidebar' }),
  );
  expect(screen.queryByText('Test dataset')).not.toBeInTheDocument();
  expect(localStorage.getItem('dataset_sidebar_collapsed')).toBe('true');
  const link = screen.getByRole('link', {
    name: 'knowledgeDetails.subbarFiles',
  });
  expect(link).toHaveAttribute('href');
  expect(
    screen.getByRole('link', { name: 'knowledgeDetails.artifacts' }),
  ).toBeInTheDocument();
  fireEvent.focus(link);
  expect(await screen.findByRole('tooltip')).toHaveTextContent(
    'knowledgeDetails.subbarFiles',
  );
  first.unmount();
  renderSidebar();
  expect(
    screen.getByRole('button', { name: 'knowledgeDetails.expandSidebar' }),
  ).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(
    screen.getByRole('button', { name: 'knowledgeDetails.expandSidebar' }),
  );
  expect(screen.getByText('Test dataset')).toBeInTheDocument();
  expect(localStorage.getItem('dataset_sidebar_collapsed')).toBe('false');
});
