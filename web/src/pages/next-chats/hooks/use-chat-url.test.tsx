import notification from '@/utils/notification';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router';
import { useChatStreamStore } from '../chat-stream/store';
import { useCreateConversationBeforeSendMessage } from './use-chat-url';

const mockCreateSession = jest.fn();
const mockUpdateSession = jest.fn();

// The session hooks are stubbed at the hook boundary on purpose: their module
// chain reaches the app router, which builds a browser router at module scope
// and needs web globals (Request) that jsdom lacks.
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

jest.mock('@/utils/notification', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}));

const mockNotificationError = jest.mocked(notification.error);

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
  const { createConversationBeforeSendMessage } =
    useCreateConversationBeforeSendMessage();
  const [outcome, setOutcome] = useState('idle');

  const handleSend = async () => {
    const data = await createConversationBeforeSendMessage('电缆标准问题');
    setOutcome(
      data
        ? `${data.targetConversationId}:${data.currentMessages.length}`
        : 'blocked',
    );
  };

  return (
    <>
      <button type="button" onClick={handleSend}>
        send
      </button>
      <span data-testid="outcome">{outcome}</span>
      <RouteProbe />
    </>
  );
}

function renderHarness(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/chat/:id" element={<Harness />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('useCreateConversationBeforeSendMessage', () => {
  beforeEach(() => {
    mockCreateSession.mockReset();
    mockUpdateSession.mockReset();
    mockNotificationError.mockReset();
    useChatStreamStore.setState({ sessions: {} });
  });

  it('creates the session before the first send and routes the question to it', async () => {
    mockCreateSession.mockResolvedValue({
      code: 0,
      data: { id: 'server-1', messages: [{ role: 'assistant', content: 'hi' }] },
    });

    renderHarness('/chat/dialog-1');

    fireEvent.click(screen.getByText('send'));

    await waitFor(() => {
      expect(screen.getByTestId('outcome')).toHaveTextContent('server-1:1');
    });
    expect(mockCreateSession).toHaveBeenCalledWith({
      chatId: 'dialog-1',
      name: '电缆标准问题',
    });
    expect(screen.getByTestId('route-conversation-id')).toHaveTextContent(
      'server-1',
    );
  });

  it('creates the session for a placeholder conversation and drops its local entry', async () => {
    mockCreateSession.mockResolvedValue({
      code: 0,
      data: { id: 'server-2', messages: [] },
    });
    useChatStreamStore.getState().ensureSession('temp-abc', 'dialog-1');

    renderHarness('/chat/dialog-1?conversationId=temp-abc&isNew=true');

    fireEvent.click(screen.getByText('send'));

    await waitFor(() => {
      expect(screen.getByTestId('outcome')).toHaveTextContent('server-2:0');
    });
    expect(useChatStreamStore.getState().sessions['temp-abc']).toBeUndefined();
    expect(screen.getByTestId('route-conversation-id')).toHaveTextContent(
      'server-2',
    );
  });

  it('reuses an existing session instead of creating another one', async () => {
    renderHarness('/chat/dialog-1?conversationId=server-9');

    fireEvent.click(screen.getByText('send'));

    await waitFor(() => {
      expect(screen.getByTestId('outcome')).toHaveTextContent('server-9:0');
    });
    expect(mockCreateSession).not.toHaveBeenCalled();
  });

  it('blocks the send when the session cannot be created', async () => {
    mockCreateSession.mockResolvedValue({
      code: 102,
      message: 'Session not found!',
      data: false,
    });

    renderHarness('/chat/dialog-1');

    fireEvent.click(screen.getByText('send'));

    await waitFor(() => {
      expect(screen.getByTestId('outcome')).toHaveTextContent('blocked');
    });
    expect(mockNotificationError).toHaveBeenCalledTimes(1);
    // Nothing may be pointed at a session the server never created.
    expect(screen.getByTestId('route-conversation-id')).toHaveTextContent(
      'none',
    );
  });

  it('blocks the send when the creation request fails outright', async () => {
    mockCreateSession.mockRejectedValue(new Error('network down'));

    renderHarness('/chat/dialog-1');

    fireEvent.click(screen.getByText('send'));

    await waitFor(() => {
      expect(screen.getByTestId('outcome')).toHaveTextContent('blocked');
    });
    expect(mockNotificationError).toHaveBeenCalledTimes(1);
  });
});
