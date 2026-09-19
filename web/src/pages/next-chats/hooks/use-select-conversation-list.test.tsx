import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router';
import { useSelectDerivedConversationList } from './use-select-conversation-list';

/** Two sessions, newest first, the way the list endpoint returns them. */
const MockConversations = [
  { id: 'server-newest', name: '最新的会话', update_time: 300 },
  { id: 'server-older', name: '较早的会话', update_time: 100 },
];

const mockSearchString = { value: '' };

// Stubbed at the hook boundary: the real session hooks reach the app router,
// which builds a browser router at module scope and needs web globals (Request)
// that jsdom lacks.
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
    useFetchChatList: () => ({ data: { chats: [], total: 0 } }),
    useFetchSessionList: () => ({
      data: MockConversations,
      loading: false,
      handleInputChange: jest.fn(),
      searchString: mockSearchString.value,
      setSearchString: jest.fn(),
    }),
  };
});

/** Shows the conversationId the route currently carries. */
function RouteProbe() {
  const [searchParams] = useSearchParams();

  return (
    <span data-testid="route-conversation-id">
      {searchParams.get('conversationId') ?? 'none'}
    </span>
  );
}

function Harness() {
  const { list } = useSelectDerivedConversationList();

  return (
    <>
      <RouteProbe />
      <span data-testid="list-head">{list[0]?.id ?? 'none'}</span>
    </>
  );
}

const renderAt = (route: string) =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/chat/:id" element={<Harness />} />
      </Routes>
    </MemoryRouter>,
  );

describe('conversation selection on entry', () => {
  beforeEach(() => {
    mockSearchString.value = '';
  });

  it('opens the first conversation when the route names none', async () => {
    renderAt('/chat/dialog-1');

    // A chat card click lands here, and the list has already been ordered by pin
    // and activity, so the head of the list is the one to open.
    await waitFor(() => {
      expect(screen.getByTestId('route-conversation-id')).toHaveTextContent(
        'server-newest',
      );
    });
  });

  it('keeps the conversation the route already names', async () => {
    renderAt('/chat/dialog-1?conversationId=server-older');

    await waitFor(() => {
      expect(screen.getByTestId('list-head')).toHaveTextContent('server-newest');
    });

    expect(screen.getByTestId('route-conversation-id')).toHaveTextContent(
      'server-older',
    );
  });

  it('leaves a placeholder conversation alone', async () => {
    renderAt('/chat/dialog-1?conversationId=temp-abc123&isNew=true');

    await waitFor(() => {
      expect(screen.getByTestId('list-head')).toHaveTextContent('server-newest');
    });

    expect(screen.getByTestId('route-conversation-id')).toHaveTextContent(
      'temp-abc123',
    );
  });
});
