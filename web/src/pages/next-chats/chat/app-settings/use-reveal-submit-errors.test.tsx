import { fireEvent, render, screen } from '@testing-library/react';
import { useRevealSubmitErrors } from './use-reveal-submit-errors';

const scrollIntoViewMock = jest.fn();

beforeAll(() => {
  Element.prototype.scrollIntoView = scrollIntoViewMock;
});

beforeEach(() => {
  scrollIntoViewMock.mockClear();
});

const Sections = ['retrieval', 'system', 'prologue', 'model'] as const;

function Harness() {
  const {
    formContainerRef,
    handleInvalidSubmit,
    openSections,
    onOpenSectionsChange,
  } = useRevealSubmitErrors(Sections, ['retrieval']);

  return (
    <form ref={formContainerRef}>
      <span data-testid="open-sections">{openSections.join(',')}</span>
      <button type="button" onClick={handleInvalidSubmit}>
        save
      </button>
      <button
        type="button"
        onClick={() => onOpenSectionsChange(['model'])}
        data-testid="open-model"
      >
        open model
      </button>
      <p id="name-form-item-message">Name is required</p>
    </form>
  );
}

describe('useRevealSubmitErrors', () => {
  it('opens only the requested section initially', () => {
    render(<Harness />);

    expect(screen.getByTestId('open-sections')).toHaveTextContent('retrieval');
  });

  it('expands every section and scrolls to the first error on invalid submit', () => {
    render(<Harness />);

    fireEvent.click(screen.getByText('save'));

    expect(screen.getByTestId('open-sections')).toHaveTextContent(
      Sections.join(','),
    );
    expect(scrollIntoViewMock).toHaveBeenCalledTimes(1);
    expect(scrollIntoViewMock).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'center',
    });
    expect(scrollIntoViewMock.mock.instances[0]).toBe(
      screen.getByText('Name is required'),
    );
  });

  it('scrolls again on every repeated invalid submit', () => {
    render(<Harness />);

    fireEvent.click(screen.getByText('save'));
    fireEvent.click(screen.getByText('save'));

    expect(scrollIntoViewMock).toHaveBeenCalledTimes(2);
  });

  it('lets the caller toggle a single section', () => {
    render(<Harness />);

    fireEvent.click(screen.getByTestId('open-model'));

    expect(screen.getByTestId('open-sections')).toHaveTextContent('model');
  });
});
