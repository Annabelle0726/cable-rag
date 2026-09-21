import { fireEvent, render, screen } from '@testing-library/react';
import ReferenceSliceCard from '..';

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options ? `${key}:${JSON.stringify(options)}` : key,
  }),
}));

jest.mock('@/components/icon-font', () => ({
  FileIcon: () => <span data-testid="file-icon" />,
}));

jest.mock('@/components/image', () => ({
  __esModule: true,
  ImageWithPopover: () => <div data-testid="chunk-image" />,
}));

beforeEach(() => {
  jest.clearAllMocks();
});

const chunk = {
  id: 'chunk-1',
  content: '<p>额定电压 <em>0.6/1kV</em> 铜芯交联聚乙烯绝缘电缆</p>',
  highlight: '',
  document_id: 'doc-1',
  document_keyword: '电缆技术要求.pdf',
  image_id: '',
  similarity: 0.9166,
  document_metadata: {
    特性阻抗: '120Ω',
    衰减: '≤ 0.5 dB/100m',
  },
} as never;

describe('a reference passage card', () => {
  it('names the passage, its document and how well it matched', () => {
    render(<ReferenceSliceCard chunk={chunk} index={1} />);

    expect(screen.getByTestId('reference-slice-index')).toHaveTextContent(
      'chunk.sliceIndex:{"index":1}',
    );
    expect(screen.getByText('电缆技术要求.pdf')).toBeInTheDocument();
    expect(screen.getByTestId('reference-slice-score')).toHaveTextContent(
      '92%',
    );
  });

  it('lays the parameters out as a key-value grid', () => {
    render(<ReferenceSliceCard chunk={chunk} index={1} />);

    const grid = screen.getByTestId('reference-slice-metadata');

    expect(grid.className).toContain('grid-cols-2');
    expect(screen.getByText('特性阻抗')).toBeInTheDocument();
    expect(screen.getByText('120Ω')).toBeInTheDocument();
    expect(screen.getByText('衰减')).toBeInTheDocument();
    expect(screen.getByText('≤ 0.5 dB/100m')).toBeInTheDocument();
  });

  it('leaves the grid out when there is nothing to put in it', () => {
    render(
      <ReferenceSliceCard
        chunk={{ ...(chunk as any), document_metadata: {} }}
        index={1}
      />,
    );

    expect(screen.queryByTestId('reference-slice-metadata')).toBeNull();
  });

  it('shows the passage with the matched terms marked, not hard-coded', () => {
    render(<ReferenceSliceCard chunk={chunk} index={1} />);
    const body = screen.getByTestId('reference-slice-content');

    // The marker styling rides on the wrapper so the backend's own <em> markup
    // is what carries the highlight, and it asks for the theme-aware accent
    // rather than a palette colour that only works on one theme.
    expect(body?.className).toContain('[&_em]:bg-accent-color-soft');
    expect(body?.className).toContain('[&_em]:text-accent-color');
    expect(body?.innerHTML).toContain('<em>0.6/1kV</em>');
  });
  it('does not paint its own theme colours', () => {
    const { container } = render(<ReferenceSliceCard chunk={chunk} index={1} />);
    const card = container.querySelector('[data-testid="reference-slice"]');

    // A surface that hard-codes a dark twin drifts the moment one theme is
    // touched; the tokens already resolve per theme.
    expect(card?.className).toContain('bg-bg-card');
    expect(card?.className).toContain('border-border-default');
    expect(card?.className).not.toMatch(/dark:/);
  });

  it('locates the passage in its document', () => {
    const onLocate = jest.fn();
    render(<ReferenceSliceCard chunk={chunk} index={2} onLocate={onLocate} />);

    fireEvent.click(screen.getByTestId('reference-slice-locate'));

    expect(onLocate).toHaveBeenCalledWith('doc-1', chunk);
  });

  it('offers no locate control when nobody can act on it', () => {
    render(<ReferenceSliceCard chunk={chunk} index={1} />);

    expect(screen.queryByTestId('reference-slice-locate')).toBeNull();
  });
});
