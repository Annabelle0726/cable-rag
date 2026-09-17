import { render, screen } from '@testing-library/react';

import MarkdownContent from '..';

// The inline citation chip is rendered from `citedChunkIndex`, which reports
// "no usable index" as -1. A caller that printed the value plainly rendered
// "图 NaN" — most visibly while an answer streamed, because the backend sends
// the reference pool with the final event only, so the pool is empty for the
// whole stream, and for a citation past the end of the pool.

jest.mock('@/constants/markdown-remark-plugins', () => ({
  MarkdownRemarkPlugins: [],
  MarkdownRemarkPluginsLite: [],
}));

jest.mock('@/constants/markdown-rehype-plugins', () => ({
  RehypeSanitizeAssistantMarkdown: {},
}));

jest.mock('unist-util-visit-parents', () => ({
  visitParents: () => {},
}));

// `react-markdown` and its rehype plugins ship as ESM only, which jest cannot
// parse. The production pipeline wraps every text node in `custom-typography`
// (see `rehypeWrapReference`), and that component is where a citation marker
// becomes a chip, so the stub hands the text straight to it.
jest.mock('react-markdown', () => ({
  __esModule: true,
  default: ({ children, components }: any) => {
    const CustomTypography = components?.['custom-typography'];
    return CustomTypography ? (
      CustomTypography({ children })
    ) : (
      <div>{children}</div>
    );
  },
}));

jest.mock('rehype-katex', () => jest.fn());
jest.mock('rehype-raw', () => jest.fn());

jest.mock('@/hooks/use-document-request', () => ({
  __esModule: true,
  useFetchDocumentThumbnailsByIds: () => ({
    setDocumentIds: () => {},
    data: {},
  }),
}));

jest.mock('@/components/image', () => ({
  __esModule: true,
  default: ({ id }: { id: string }) => <div data-testid="doc-image" data-id={id} />,
  AuthenticatedImg: ({ src }: { src?: string }) => <img src={src} alt="" />,
}));

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) =>
      ({
        'common.figure': '图',
        'chat.searching': 'Searching',
        'chat.thinking': 'Thinking',
        'chat.thought': 'Thought',
        'chat.agenticLog': 'Log',
        'chat.retrieving': 'Retrieving',
      })[key] ?? key,
  }),
}));

jest.mock('react-syntax-highlighter', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <pre>{children}</pre>
  ),
}));

jest.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  oneDark: {},
  oneLight: {},
}));

const renderContent = (content: string, chunks: unknown[] = []) =>
  render(
    <MarkdownContent
      content={content}
      loading={false}
      reference={{ chunks } as never}
    />,
  );

const fiveChunks = Array.from({ length: 5 }, (_, index) => ({
  id: `chunk-${index + 1}`,
  content_with_weight: `第 ${index + 1} 段`,
}));

describe('inline citation chip', () => {
  it('renders the figure number of a marker that resolves', () => {
    const { container } = renderContent('见表 [ID:5]。', fiveChunks);

    expect(screen.getByText(/图\s*5/)).toBeInTheDocument();
    expect(container.textContent).not.toContain('NaN');
  });

  it('keeps the citation number as plain text while the pool is still empty', () => {
    const { container } = renderContent('见表 [ID:1]。', []);

    // react-string-replace splits on the regex capture group, so the fallback
    // receives the number alone — no chip, no `图 NaN`, no broken reference.
    expect(container.textContent).toBe('见表 1。');
  });

  it('keeps the citation number as plain text when it points past the end of the pool', () => {
    const { container } = renderContent('见表 [ID:6]。', fiveChunks);

    expect(container.textContent).toBe('见表 6。');
    expect(container.textContent).not.toContain('图');
  });

  it('renders no chip for marker 0, which 1-based citations never emit', () => {
    const { container } = renderContent('见表 [ID:0]。', fiveChunks);

    expect(container.textContent).toBe('见表 0。');
    expect(container.textContent).not.toContain('图');
  });

  it('renders the chip for a resolvable marker next to an unresolvable one', () => {
    const { container } = renderContent('见表 [ID:6]，另见 [ID:2]。', fiveChunks);

    expect(container.textContent).toContain('图 2');
    expect(container.textContent).toContain('6');
    expect(container.textContent).not.toContain('NaN');
  });
});
