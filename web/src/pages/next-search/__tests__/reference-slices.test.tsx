import { fireEvent, render, screen } from '@testing-library/react';
import ReferenceSlices from '../reference-slices';

// A search result page used to render every retrieved passage at once: a tuned
// corpus returned thirty-odd slices, which pushed the related-search links and
// the pagination summary off the first screen. The list opens at five and keeps
// the rest behind one control, so the tests below pin both ends of that.

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { count?: number }) =>
      options?.count === undefined ? key : `${key}:${options.count}`,
  }),
}));

jest.mock('@/components/icon-font', () => ({
  FileIcon: () => <span data-testid="file-icon" />,
}));

jest.mock('@/components/image', () => ({
  __esModule: true,
  ImageWithPopover: () => <div data-testid="chunk-image" />,
}));

const makeChunks = (count: number) =>
  Array.from({ length: count }, (_, index) => ({
    id: `chunk-${index + 1}`,
    content: `<p>内容 ${index + 1}</p>`,
    highlight: '',
    document_id: `doc-${index + 1}`,
    document_keyword: `文档 ${index + 1}`,
    image_id: '',
  })) as never[];

describe('reference slice list', () => {
  it('opens with five passages and hides the rest behind a control', () => {
    render(
      <ReferenceSlices chunks={makeChunks(12)} onOpenDocument={jest.fn()} />,
    );

    expect(screen.getAllByTestId('reference-slice')).toHaveLength(5);
    expect(screen.getByTestId('reference-slices-toggle')).toHaveTextContent(
      'search.expandSlices:7',
    );
  });

  it('renders every passage once the reader asks for them, and folds them back', () => {
    render(
      <ReferenceSlices chunks={makeChunks(12)} onOpenDocument={jest.fn()} />,
    );

    fireEvent.click(screen.getByTestId('reference-slices-toggle'));

    expect(screen.getAllByTestId('reference-slice')).toHaveLength(12);
    expect(screen.getByTestId('reference-slices-toggle')).toHaveTextContent(
      'search.collapseSlices',
    );

    fireEvent.click(screen.getByTestId('reference-slices-toggle'));

    expect(screen.getAllByTestId('reference-slice')).toHaveLength(5);
  });

  it('shows no control when the whole list already fits', () => {
    render(
      <ReferenceSlices chunks={makeChunks(5)} onOpenDocument={jest.fn()} />,
    );

    expect(screen.getAllByTestId('reference-slice')).toHaveLength(5);
    expect(screen.queryByTestId('reference-slices-toggle')).toBeNull();
  });

  it('opens the document of the passage that was clicked', () => {
    const onOpenDocument = jest.fn();
    render(
      <ReferenceSlices
        chunks={makeChunks(3)}
        onOpenDocument={onOpenDocument}
      />,
    );

    // The card's locate control, not the file tag: the tag is a label.
    fireEvent.click(screen.getAllByTestId('reference-slice-locate')[1]);

    expect(onOpenDocument).toHaveBeenCalledWith(
      'doc-2',
      expect.objectContaining({ id: 'chunk-2' }),
    );
  });
});
