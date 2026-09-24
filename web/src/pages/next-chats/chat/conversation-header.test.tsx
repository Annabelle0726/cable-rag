import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { ConversationHeader } from './conversation-header';

const mockCreateSession = jest.fn();
const mockUpdateSession = jest.fn();

// The session hooks reach the app router at module scope; the model selector
// fetches the tenant's model list. Both are stubbed at their boundary so this
// test only covers the header's own layout and wiring — which is also why the
// header must not resolve its own datasets: rendering it here would then build
// the app router and fail on the web globals jsdom lacks.
jest.mock('@/hooks/use-chat-request', () => {
  const { useSearchParams } = require('react-router');
  const { ChatSearchParams } = require('@/constants/chat');

  return {
    useGetChatSearchParams: () => {
      const [searchParams] = useSearchParams();

      return {
        dialogId: searchParams.get(ChatSearchParams.DialogId) || '',
        conversationId: searchParams.get(ChatSearchParams.ConversationId) || '',
        isNew: searchParams.get(ChatSearchParams.isNew) || '',
      };
    },
    useCreateSession: () => ({
      createSession: mockCreateSession,
      loading: false,
    }),
    useUpdateSession: () => ({
      updateSession: mockUpdateSession,
      loading: false,
    }),
  };
});

jest.mock('@/components/model-tree-select', () => ({
  ModelTreeSelect: ({ onChange }: { onChange?: (value: string) => void }) => (
    <button
      type="button"
      data-testid="model-select"
      onClick={() => onChange?.('model-2')}
    >
      model
    </button>
  ),
}));

function renderHeader(
  onModelChange = jest.fn(),
  onOpenSettings = jest.fn(),
  datasets: Array<{ id: string; label: string }> = [],
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/chat/dialog-1?conversationId=server-1']}>
        <Routes>
          <Route
            path="/chat/:id"
            element={
              <ConversationHeader
                sessionId="server-1"
                title="QA - R2"
                llmId="model-1"
                onModelChange={onModelChange}
                datasets={datasets}
                onOpenSettings={onOpenSettings}
                onExpandSessions={jest.fn()}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  return { onModelChange, onOpenSettings };
}

describe('ConversationHeader', () => {
  it('keeps the row to the title, the settings entry and the session list control', () => {
    renderHeader();

    expect(screen.getByTestId('chat-detail-title')).toHaveTextContent(
      'QA - R2',
    );
    expect(screen.getByTestId('chat-settings-header')).toBeInTheDocument();
    expect(
      screen.getByTestId('chat-detail-sessions-open-header'),
    ).toBeInTheDocument();
    // The multi-model entry lives in the settings drawer, not in this row.
    expect(screen.queryByTestId('chat-detail-multimodel-toggle')).toBeNull();
  });

  it('opens the settings drawer from its own button', () => {
    const { onOpenSettings } = renderHeader();

    fireEvent.click(screen.getByTestId('chat-settings-header'));

    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });

  it('switches the model from the name dropdown', () => {
    const { onModelChange } = renderHeader();

    expect(screen.queryByTestId('model-select')).toBeNull();

    fireEvent.click(screen.getByTestId('chat-detail-header-toggle'));
    fireEvent.click(screen.getByTestId('model-select'));

    expect(onModelChange).toHaveBeenCalledWith('model-2');
  });
});

// The page names the datasets and this row only shows them, so what is covered
// here is the row's own contract: the labels it is handed, and the click that
// hands the panel back to the page. A tag opens the chat settings drawer — the
// same panel as the settings entry beside it — because that is where a
// conversation's datasets are changed.
describe('the dataset tags', () => {
  const BoundDatasets = [
    { id: 'kb-1', label: '国标知识库' },
    { id: 'kb-2', label: '电缆工艺库' },
  ];

  it('renders the names it is given and opens the settings drawer from a tag', () => {
    const { onOpenSettings } = renderHeader(
      jest.fn(),
      jest.fn(),
      BoundDatasets,
    );

    const tags = screen.getByTestId('chat-detail-dataset-tags');

    expect(tags).toHaveTextContent('国标知识库');
    expect(tags).toHaveTextContent('电缆工艺库');

    fireEvent.click(screen.getByText('电缆工艺库'));

    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });

  it('summarises past the third dataset instead of crowding the title', () => {
    const { onOpenSettings } = renderHeader(jest.fn(), jest.fn(), [
      { id: 'kb-1', label: 'first' },
      { id: 'kb-2', label: 'second' },
      { id: 'kb-3', label: 'third' },
      { id: 'kb-4', label: 'fourth' },
      { id: 'kb-5', label: 'fifth' },
    ]);

    expect(screen.getAllByTestId('chat-detail-dataset-tag')).toHaveLength(4);
    expect(screen.getByText('+2')).toBeInTheDocument();
    expect(screen.queryByText('fourth')).toBeNull();

    fireEvent.click(screen.getByText('+2'));

    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });

  it('leaves the row without tags when the conversation has none', () => {
    renderHeader(jest.fn(), jest.fn(), []);

    expect(screen.queryByTestId('chat-detail-dataset-tags')).toBeNull();
  });
});
