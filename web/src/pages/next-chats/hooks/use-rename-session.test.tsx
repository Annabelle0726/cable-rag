import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router';
import { useChatStreamStore } from '../chat-stream/store';
import { useRenameSession } from './use-rename-session';

const mockCreateSession = jest.fn();
const mockUpdateSession = jest.fn();

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

function RouteProbe() {
  const [searchParams] = useSearchParams();

  return (
    <span data-testid="route-conversation-id">
      {searchParams.get('conversationId') ?? 'none'}
    </span>
  );
}

function Harness({ sessionId }: { sessionId: string }) {
  const { renameSession } = useRenameSession();
  const [outcome, setOutcome] = useState('idle');

  const handleRename = async () => {
    const renamed = await renameSession({ sessionId, name: ' 电缆标准查询 ' });
    setOutcome(renamed ? 'renamed' : 'failed');
  };

  return (
    <>
      <button type="button" onClick={handleRename}>
        rename
      </button>
      <span data-testid="outcome">{outcome}</span>
      <RouteProbe />
    </>
  );
}

function renderHarness(sessionId: string, initialEntry = '/chat/dialog-1') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/chat/:id" element={<Harness sessionId={sessionId} />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('useRenameSession', () => {
  beforeEach(() => {
    mockCreateSession.mockReset();
    mockUpdateSession.mockReset();
    useChatStreamStore.setState({ sessions: {} });
  });

  it('patches a session the server already stores', async () => {
    mockUpdateSession.mockResolvedValue({ code: 0, data: true });

    renderHarness('server-1');

    fireEvent.click(screen.getByText('rename'));

    await waitFor(() => {
      expect(screen.getByTestId('outcome')).toHaveTextContent('renamed');
    });
    expect(mockUpdateSession).toHaveBeenCalledWith({
      chatId: 'dialog-1',
      sessionId: 'server-1',
      params: { name: '电缆标准查询' },
    });
    expect(mockCreateSession).not.toHaveBeenCalled();
  });

  it('creates the session when naming a placeholder, instead of patching a missing row', async () => {
    mockCreateSession.mockResolvedValue({
      code: 0,
      data: { id: 'server-7', messages: [] },
    });
    useChatStreamStore.getState().ensureSession('temp-abc', 'dialog-1');

    renderHarness('temp-abc', '/chat/dialog-1?conversationId=temp-abc&isNew=true');

    fireEvent.click(screen.getByText('rename'));

    await waitFor(() => {
      expect(screen.getByTestId('outcome')).toHaveTextContent('renamed');
    });
    expect(mockCreateSession).toHaveBeenCalledWith({
      chatId: 'dialog-1',
      name: '电缆标准查询',
    });
    expect(mockUpdateSession).not.toHaveBeenCalled();
    // Wait for the route: the rename writes it from the promise continuation and
    // react-router commits that navigation on its own schedule, so reading it
    // straight after the outcome above races it.
    await waitFor(() => {
      expect(screen.getByTestId('route-conversation-id')).toHaveTextContent(
        'server-7',
      );
    });
    expect(useChatStreamStore.getState().sessions['temp-abc']).toBeUndefined();
  });

  it('does not navigate when the renamed placeholder is not the open conversation', async () => {
    mockCreateSession.mockResolvedValue({
      code: 0,
      data: { id: 'server-8', messages: [] },
    });

    renderHarness(
      'temp-xyz',
      '/chat/dialog-1?conversationId=server-open&isNew=false',
    );

    fireEvent.click(screen.getByText('rename'));

    await waitFor(() => {
      expect(screen.getByTestId('outcome')).toHaveTextContent('renamed');
    });
    expect(mockCreateSession).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('route-conversation-id')).toHaveTextContent(
      'server-open',
    );
  });

  it('reports failure and keeps the route untouched when creation fails', async () => {    mockCreateSession.mockResolvedValue({
      code: 500,
      message: 'boom',
      data: false,
    });

    renderHarness('temp-abc', '/chat/dialog-1?conversationId=temp-abc&isNew=true');

    fireEvent.click(screen.getByText('rename'));

    await waitFor(() => {
      expect(screen.getByTestId('outcome')).toHaveTextContent('failed');
    });
    expect(screen.getByTestId('route-conversation-id')).toHaveTextContent(
      'temp-abc',
    );
  });

  it('reports failure when the patch is rejected', async () => {
    mockUpdateSession.mockResolvedValue({
      code: 102,
      message: 'Session not found!',
    });

    renderHarness('server-gone');

    fireEvent.click(screen.getByText('rename'));

    await waitFor(() => {
      expect(screen.getByTestId('outcome')).toHaveTextContent('failed');
    });
  });
});
