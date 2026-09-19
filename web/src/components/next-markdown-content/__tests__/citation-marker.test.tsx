import { fireEvent, render, screen } from '@testing-library/react';

import NextMarkdownContent from '..';

// The chat transcript renders through this component, and the citation chip is
// built from `citedChunkIndex`, which reports "no usable index" as -1. The
// fallback used to print that index on its own — the regex capture group, without
// the `[ID:…]` wrapper — so `[ID:1][ID:3][ID:5]` reached the screen as `135`:
// three citations that read as one number, with nothing to hover and no way to
// tell them apart from the sentence. A live run hit exactly that, because the tool
// loop answered from the conversation history (no retrieval, so no pool) while the
// model quoted the previous answer's markers verbatim.

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
  defaultUrlTransform: (url: string) => url,
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
  default: ({ id }: { id: string }) => (
    <div data-testid="doc-image" data-id={id} />
  ),
  AuthenticatedImg: ({ src }: { src?: string }) => <img src={src} alt="" />,
}));

jest.mock('react-i18next', () => ({
  // The component's import chain reaches `@/locales/config`, which calls
  // `i18n.use(initReactI18next)` at module scope, so the mock has to carry the
  // plugin object as well as the hook this suite actually stubs.
  initReactI18next: { type: '3rdParty', init: () => {} },
  useTranslation: () => ({
    t: (key: string) =>
      ({
        'common.figure': '图',
        'chat.citationUnresolved': '该引用未能对应到证据片段',
        'chat.thinking': 'Thinking',
        'chat.thought': 'Thought',
        'chat.agenticLog': 'Log',
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

const fiveChunks = Array.from({ length: 5 }, (_, index) => ({
  id: `chunk-${index + 1}`,
  content_with_weight: `第 ${index + 1} 段`,
  document_id: `doc-${index + 1}`,
}));

// `getReferenceInfo` resolves a chunk's document through `doc_aggs`, and the
// click path needs the file extension it carries.
const documentAggs = fiveChunks.map((chunk) => ({
  doc_id: chunk.document_id,
  doc_name: `${chunk.document_id}.pdf`,
}));

const renderContent = (
  content: string,
  chunks: unknown[] = [],
  clickDocumentButton?: (documentId: string, chunk: unknown) => void,
) =>
  render(
    <NextMarkdownContent
      content={content}
      loading={false}
      reference={{ chunks, doc_aggs: documentAggs } as never}
      clickDocumentButton={clickDocumentButton as never}
    />,
  );

/** Everything the reader sees, with the collapsed log panels taken out. */
const answerBody = (container: HTMLElement) =>
  (container.textContent ?? '').replace(/\s+/g, '');

describe('citation markers in the chat transcript', () => {
  it('marks a citation that resolves, and it opens a passage', () => {
    const { container } = renderContent('见表 [ID:5]。', fiveChunks);

    expect(screen.getByText('[5]')).toBeInTheDocument();
    expect(answerBody(container)).not.toContain('NaN');
  });

  it('keeps a consecutive run separated when the pool is empty', () => {
    const { container } = renderContent(
      '如有冲突以该表为准 [ID:1][ID:3][ID:5]。',
      [],
    );

    // The regression: `135` — one number where three citations belong.
    expect(answerBody(container)).toContain('以该表为准[1][3][5]。');
    expect(answerBody(container)).not.toContain('135');
  });

  it('keeps the marker readable but not interactive when it points past the pool', () => {
    const { container } = renderContent('见表 [ID:6]。', fiveChunks);

    expect(answerBody(container)).toContain('[6]');
    // A dashed rim is what separates "a citation that could not be opened" from
    // plain text and from the solid-rimmed chip that resolves — the state the
    // reported answer was in, where the marker read as ordinary prose.
    expect(screen.getByTestId('citation-unresolved').className).toContain(
      'border-dashed',
    );
    expect(screen.getByTitle('该引用未能对应到证据片段')).toBeInTheDocument();
  });

  it('carries no bare number out of a run that mixes resolvable and unresolvable markers', () => {
    const { container } = renderContent('见表 [ID:6]，另见 [ID:2]。', fiveChunks);

    expect(screen.getByText('[2]')).toBeInTheDocument();
    expect(answerBody(container)).toContain('[6]');
    expect(answerBody(container)).not.toContain('NaN');
  });

  it('renders a resolvable marker as something that reads and behaves as a link', () => {
    renderContent('见表 [ID:5]。', fiveChunks);

    // The reported defect: a chip coloured two RGB units off the page with
    // `cursor: auto` and no handler read as ordinary prose, so nobody hovered it
    // and the working popover went unnoticed. It has to carry the app's link
    // colour, a pointer cursor, and be a real control.
    const chip = screen.getByText('[5]');
    const control = chip.closest('button') as HTMLElement;

    expect(control).not.toBeNull();
    expect(control.className).toContain('text-accent-primary');
    expect(control.className).toContain('cursor-pointer');
    expect(control.className).toContain('hover:bg-accent-primary');
  });

  it('opens the passage a marker points at when it is clicked', () => {
    const clicked: Array<{ documentId: unknown; chunk: unknown }> = [];
    const clickDocumentButton = (documentId: unknown, chunk: unknown) => {
      clicked.push({ documentId, chunk });
    };
    renderContent('见表 [ID:5]。', fiveChunks, clickDocumentButton);

    fireEvent.click(screen.getByText('[5]'));

    expect(clicked).toHaveLength(1);
    expect(clicked[0].documentId).toBe('doc-5');
    expect((clicked[0].chunk as { id: string }).id).toBe('chunk-5');
  });

  it('does not make an unopenable marker clickable', () => {
    const clicked: unknown[] = [];
    renderContent('见表 [ID:9]。', fiveChunks, (...args: unknown[]) =>
      clicked.push(args),
    );

    fireEvent.click(screen.getByTestId('citation-unresolved'));

    expect(clicked).toHaveLength(0);
  });
});
