import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { LucideDatabase } from 'lucide-react';
import { MemoryRouter } from 'react-router';
import { DatasetNavMenu } from '../dataset-nav-menu';

/** Two knowledge bases, one per class, so switching the first level is visible. */
const MockDatasets = [
  {
    id: 'kb-bom',
    name: 'BOM 结构库',
    document_count: 3,
    description: '',
  },
  {
    id: 'kb-gb',
    name: 'GB/T 标准规范',
    document_count: 5,
    description: '',
  },
];

jest.mock('@/hooks/use-knowledge-request', () => ({
  useFetchKnowledgeList: () => ({ list: MockDatasets, loading: false }),
}));

jest.mock('@/hooks/logic-hooks/navigate-hooks', () => ({
  useNavigatePage: () => ({ navigateToDatasetList: jest.fn() }),
}));

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => (key === 'datasetCategory.empty' ? '暂无知识库' : key),
  }),
}));

// The route table builds a browser router on import, which jsdom cannot host;
// only the two paths this component links to are needed here.
jest.mock('@/routes', () => ({
  Routes: { Dataset: '/dataset', Datasets: '/datasets' },
}));

const OriginalResizeObserver = globalThis.ResizeObserver;

beforeAll(() => {
  // Radix positions the panel with floating-ui, which observes element resizes.
  globalThis.ResizeObserver = jest.fn().mockImplementation(() => ({
    observe: jest.fn(),
    unobserve: jest.fn(),
    disconnect: jest.fn(),
  }));
});

afterAll(() => {
  globalThis.ResizeObserver = OriginalResizeObserver;
});

const renderMenu = () =>
  render(
    <MemoryRouter>
      <DatasetNavMenu
        to="/datasets"
        label="数据集"
        icon={LucideDatabase}
        isActive={false}
        testId="nav-dataset"
        className="nav-link"
      />
    </MemoryRouter>,
  );

describe('knowledge base navigation menu', () => {
  it('keeps the navigation link as the trigger', () => {
    renderMenu();

    expect(screen.getByTestId('nav-dataset')).toHaveTextContent('数据集');
  });

  it('stays closed until the pointer reaches it', () => {
    renderMenu();

    expect(screen.queryByTestId('nav-dataset-menu')).not.toBeInTheDocument();
  });

  it('opens both levels on hover, listing the highlighted class only', async () => {
    renderMenu();

    fireEvent.mouseEnter(screen.getByTestId('nav-dataset'));

    await waitFor(() => {
      expect(screen.getByTestId('nav-dataset-category-bom')).toBeInTheDocument();
    });

    // First level: the five industrial classes, with the custom class folded
    // into the general bucket rather than listed as its own entry.
    expect(
      screen.getByTestId('nav-dataset-category-standard'),
    ).toBeInTheDocument();
    expect(screen.getByTestId('nav-dataset-category-spec')).toBeInTheDocument();
    expect(
      screen.getByTestId('nav-dataset-category-quality'),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId('nav-dataset-category-general'),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId('nav-dataset-category-custom'),
    ).not.toBeInTheDocument();

    // Second level: the knowledge base of the highlighted class only.
    expect(screen.getByText('BOM 结构库')).toBeInTheDocument();
    expect(screen.queryByText('GB/T 标准规范')).not.toBeInTheDocument();
  });

  it('switches the second level when another class is highlighted', async () => {
    renderMenu();

    fireEvent.mouseEnter(screen.getByTestId('nav-dataset'));

    await waitFor(() => {
      expect(
        screen.getByTestId('nav-dataset-category-standard'),
      ).toBeInTheDocument();
    });

    fireEvent.mouseEnter(screen.getByTestId('nav-dataset-category-standard'));

    await waitFor(() => {
      expect(screen.getByText('GB/T 标准规范')).toBeInTheDocument();
    });

    expect(screen.queryByText('BOM 结构库')).not.toBeInTheDocument();
  });

  it('offers the create shortcut below the list', async () => {
    renderMenu();

    fireEvent.mouseEnter(screen.getByTestId('nav-dataset'));

    await waitFor(() => {
      expect(screen.getByTestId('nav-dataset-new')).toBeInTheDocument();
    });

    expect(screen.getByTestId('nav-dataset-new')).toHaveTextContent(
      'knowledgeList.createKnowledgeBase',
    );
  });
});
