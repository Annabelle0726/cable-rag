import { TooltipProvider } from '@/components/ui/tooltip';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { Sessions } from './sessions';

/** One pinned conversation and one plain one, newest first. */
const MockConversations = [
  {
    id: 'server-pinned',
    name: '国标查询',
    is_pinned: true,
    update_time: 300,
    is_new: false,
  },
  {
    id: 'server-plain',
    name: '临时问题',
    is_pinned: false,
    update_time: 100,
    is_new: false,
  },
];

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
    useFetchChat: () => ({ data: { icon: '', name: '线缆助手' } }),
    useRemoveSessions: () => ({ removeSessions: jest.fn() }),
    usePinSession: () => ({ pinSession: jest.fn(), loading: false }),
    useCreateSession: () => ({ createSession: jest.fn(), loading: false }),
    useUpdateSession: () => ({ updateSession: jest.fn(), loading: false }),
  };
});

jest.mock('@/pages/next-chats/hooks/use-select-conversation-list', () => ({
  useSelectDerivedConversationList: () => ({
    list: MockConversations,
    addTemporaryConversation: jest.fn(),
    removeTemporaryConversation: jest.fn(),
    handleInputChange: jest.fn(),
    searchString: '',
    loading: false,
  }),
  useFindPrologueFromDialogList: () => undefined,
}));

jest.mock('../hooks/use-rename-session', () => ({
  useRenameSession: () => ({ renameSession: jest.fn(), loading: false }),
}));

const renderSessions = (route: string, loadingConversationId?: string) =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <TooltipProvider>
        <Routes>
          <Route
            path="/chat/:id"
            element={
              <Sessions
                handleConversationCardClick={jest.fn()}
                visible
                onVisibleChange={jest.fn()}
                onOpenSettings={jest.fn()}
                loadingConversationId={loadingConversationId}
              />
            }
          />
        </Routes>
      </TooltipProvider>
    </MemoryRouter>,
  );

const rowFor = (name: string) =>
  screen.getByText(name).closest('li') as HTMLElement;

describe('pinned conversations in the list', () => {
  it('marks a pinned row with a pin and a surface of its own', () => {
    renderSessions('/chat/dialog-1');

    const row = rowFor('国标查询');

    expect(
      row.querySelector("[data-testid='chat-detail-session-pin-marker']"),
    ).not.toBeNull();
    expect(row.className).toContain('bg-cable-surface-muted');
    expect(row.className).toContain('border-cable-hairline');
  });

  it('leaves an unpinned row as it was', () => {
    renderSessions('/chat/dialog-1');

    const row = rowFor('临时问题');

    expect(
      row.querySelector("[data-testid='chat-detail-session-pin-marker']"),
    ).toBeNull();
    expect(row.className).not.toContain('bg-cable-surface-muted');
    expect(row.className).not.toContain('border-l-cable-accent');
  });

  it('puts the brand bar on the pinned row that is open', () => {
    renderSessions('/chat/dialog-1?conversationId=server-pinned');

    const row = rowFor('国标查询');

    // The open row keeps the selected highlight, so the bar is what has to say
    // it is pinned as well.
    expect(row.className).toContain('border-l-2');
    expect(row.className).toContain('border-l-cable-accent');
    expect(row).toHaveAttribute('aria-selected', 'true');
  });
});

// The row whose messages are in flight reports it itself, so the rail answers the
// click even when the transcript is still empty.
describe('the session being fetched', () => {
  it('swaps its rename action for a spinner and marks the row busy', () => {
    renderSessions('/chat/dialog-1', 'server-pinned');

    const row = rowFor('国标查询');

    expect(
      row.querySelector("[data-testid='chat-detail-session-loading']"),
    ).not.toBeNull();
    expect(
      row.querySelector("[data-testid='chat-detail-session-rename']"),
    ).toBeNull();
    expect(row).toHaveAttribute('aria-busy', 'true');
  });

  it('refuses a second click while its request is in flight', () => {
    renderSessions('/chat/dialog-1', 'server-pinned');

    const button = rowFor('国标查询').querySelector(
      "[data-testid='chat-detail-session-item']",
    ) as HTMLButtonElement;

    expect(button.disabled).toBe(true);
  });

  it('leaves every other row with its own actions', () => {
    renderSessions('/chat/dialog-1', 'server-pinned');

    const other = rowFor('临时问题');

    expect(
      other.querySelector("[data-testid='chat-detail-session-rename']"),
    ).not.toBeNull();
    expect(
      other.querySelector("[data-testid='chat-detail-session-loading']"),
    ).toBeNull();
    expect(other).not.toHaveAttribute('aria-busy');
  });
});
