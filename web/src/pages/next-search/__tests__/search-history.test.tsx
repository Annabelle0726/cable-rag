import { fireEvent, render, screen } from '@testing-library/react';
import SearchHistory from '../search-history';
import { useSearchHistoryStore } from '../search-history-store';

// The history is a shortcut rail under the search box: five entries, newest
// first, kept in the browser. The list is capped and de-duplicated because the
// row has to stay one line, and a question asked twice belongs at the front
// rather than twice in the list.

const store = useSearchHistoryStore;

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe('search history store', () => {
  beforeEach(() => {
    window.localStorage.clear();
    store.setState({ entries: [] });
  });

  it('keeps the five most recent questions, newest first', () => {
    ['q1', 'q2', 'q3', 'q4', 'q5', 'q6'].forEach((question) =>
      store.getState().remember(question),
    );

    expect(store.getState().entries).toEqual(['q6', 'q5', 'q4', 'q3', 'q2']);
  });

  it('moves a repeated question to the front instead of listing it twice', () => {
    ['q1', 'q2', 'q3'].forEach((question) =>
      store.getState().remember(question),
    );

    store.getState().remember('q1');

    expect(store.getState().entries).toEqual(['q1', 'q3', 'q2']);
  });

  it('survives a reload by writing to localStorage', () => {
    store.getState().remember(' 火花试验电压 ');

    expect(
      JSON.parse(window.localStorage.getItem('ragflow-search-history') || '[]'),
    ).toEqual(['火花试验电压']);
  });

  it('ignores a blank question', () => {
    store.getState().remember('   ');

    expect(store.getState().entries).toEqual([]);
  });

  it('clears the stored list', () => {
    store.getState().remember('q1');
    store.getState().clear();

    expect(store.getState().entries).toEqual([]);
    expect(
      JSON.parse(window.localStorage.getItem('ragflow-search-history') || '[]'),
    ).toEqual([]);
  });
});

describe('search history tags', () => {
  beforeEach(() => {
    window.localStorage.clear();
    store.setState({ entries: [] });
  });

  it('renders nothing while there is no history', () => {
    render(<SearchHistory onSelect={jest.fn()} />);

    expect(screen.queryByTestId('search-history')).toBeNull();
  });

  it('hands the clicked tag back to the caller', () => {
    const onSelect = jest.fn();
    store.getState().remember('电缆技术要求');
    render(<SearchHistory onSelect={onSelect} />);

    fireEvent.click(screen.getByText('电缆技术要求'));

    expect(onSelect).toHaveBeenCalledWith('电缆技术要求');
  });

  it('empties the rail from the clear button', () => {
    store.getState().remember('电缆技术要求');
    render(<SearchHistory onSelect={jest.fn()} />);

    fireEvent.click(screen.getByTestId('search-history-clear'));

    expect(screen.queryByTestId('search-history')).toBeNull();
  });
});
