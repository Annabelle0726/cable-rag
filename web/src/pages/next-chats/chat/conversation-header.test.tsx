import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { ConversationHeader } from './conversation-header';

const mockCreateSession = jest.fn();
const mockUpdateSession = jest.fn();

// The session hooks reach the app router at module scope; the model selector
// fetches the tenant's model list. Both are stubbed at their boundary so this
// test only covers the header's own layout and wiring.
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

function renderHeader(onModelChange = jest.fn(), onOpenSettings = jest.fn()) {
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

    expect(screen.getByTestId('chat-detail-title')).toHaveTextContent('QA - R2');
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
