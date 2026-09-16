import { Button } from '@/components/ui/button';
import {
  useFetchChat,
  useFetchSessionList,
  useFetchSessionManually,
  useGetChatSearchParams,
  usePatchChat,
} from '@/hooks/use-chat-request';
import { useSetModalState } from '@/hooks/common-hooks';
import { IClientConversation } from '@/interfaces/database/chat';
import { RootLayoutContainer } from '@/layouts/root-layout';
import { cn } from '@/lib/utils';
import { isPersistedConversationId } from '@/utils/chat';
import { isEmpty } from 'lodash';
import { LucideArrowBigLeft } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';
import { useHandleClickConversationCard } from '../hooks/use-click-card';
import { useChatUrlParams } from '../hooks/use-chat-url';
import { ChatSettings } from './app-settings/chat-settings';
import { MultipleChatBox } from './chat-box/next-multiple-chat-box';
import { SingleChatBox } from './chat-box/single-chat-box';
import { ConversationHeader } from './conversation-header';
import { Sessions } from './sessions';
import { useAddChatBox } from './use-add-box';
import { useSwitchDebugMode } from './use-switch-debug-mode';

export default function Chat() {
  const { t } = useTranslation();
  const [currentConversation, setCurrentConversation] =
    useState<IClientConversation>({} as IClientConversation);

  const { fetchSessionManually } = useFetchSessionManually();

  const { handleConversationCardClick, controller, stopOutputMessage } =
    useHandleClickConversationCard();

  const { isDebugMode, switchDebugMode } = useSwitchDebugMode();
  const { removeChatBox, addChatBox, chatBoxIds, hasSingleChatBox } =
    useAddChatBox(isDebugMode);

  const { conversationId } = useGetChatSearchParams();
  const { id: chatId } = useParams();
  const { clearConversationParams } = useChatUrlParams();

  const { data: dialogList } = useFetchSessionList();
  const { data: currentDialog } = useFetchChat();
  const { patchChat } = usePatchChat();

  // Lifted out of `Sessions` so the header can mirror it: while the conversation
  // list is open the header drops its title (the list already highlights the
  // active conversation), and it reappears once the list is collapsed.
  const [sessionsVisible, setSessionsVisible] = useState(true);

  const handleExpandSessions = useCallback(() => {
    setSessionsVisible(true);
  }, []);

  /**
   * The header's model dropdown writes straight to the chat record with a
   * partial PATCH — it resolves the paired tenant model id server-side and
   * leaves every other field alone. The settings drawer reads the same record,
   * so it opens on the new model.
   */
  const handleModelChange = useCallback(
    (nextLlmId: string) => {
      if (!chatId || !nextLlmId || nextLlmId === currentDialog?.llm_id) {
        return;
      }
      patchChat({ chatId, params: { llm_id: nextLlmId } });
    },
    [chatId, currentDialog?.llm_id, patchChat],
  );

  // The settings drawer is owned here: both of its triggers (the conversation
  // list header, and the chat header that only shows while the list is
  // collapsed) open the same panel.
  const {
    visible: settingsVisible,
    showModal: showSettings,
    hideModal: hideSettings,
  } = useSetModalState();

  // The multi-model comparison view is entered from the settings drawer's model
  // section, not from the header, which keeps that row to one line.
  const handleOpenMultiModel = useCallback(() => {
    hideSettings();
    switchDebugMode();
  }, [hideSettings, switchDebugMode]);

  const currentConversationName = useMemo(() => {
    return (
      dialogList.find((x) => x.id === conversationId)?.name ||
      t('chat.newConversation')
    );
  }, [conversationId, dialogList, t]);

  // The URL is the single source of truth for which conversation is open:
  // card clicks, "+" and the temp→real id swap after the first send all land
  // here. Clear first so the previous conversation's messages and references
  // can never leak into the newly opened one while the fetch is in flight.
  useEffect(() => {
    setCurrentConversation((previous) =>
      isEmpty(previous) ? previous : ({} as IClientConversation),
    );
    // A placeholder conversation has no server row to fetch, so only a persisted
    // id is worth a request — the placeholder's messages come from the prologue
    // seeded in the stream store.
    if (!isPersistedConversationId(conversationId)) return;

    let cancelled = false;
    fetchSessionManually(conversationId).then((conversation) => {
      if (cancelled) {
        return;
      }
      if (!conversation) {
        // The session is gone (deleted elsewhere, stale link, or a temp id that
        // never reached the server). Drop the dead id so this page settles into a
        // blank conversation instead of showing an empty shell; the request itself
        // already suppressed the "102 Session not found" toast.
        clearConversationParams();
        return;
      }
      if (!isEmpty(conversation)) {
        setCurrentConversation(conversation);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [conversationId, fetchSessionManually, clearConversationParams]);

  if (isDebugMode) {
    return (
      <section
        className="pt-5 pb-14 h-[100vh] flex flex-col"
        data-testid="chat-detail-multimodel-root"
      >
        <header className="px-10 pb-5">
          <div className="mb-5">
            <Button
              variant="outline"
              onClick={switchDebugMode}
              data-testid="chat-detail-multimodel-back"
            >
              <LucideArrowBigLeft />
              <span>{t('common.back')}</span>
            </Button>
          </div>

          <span className="text-2xl">
            {t('chat.multipleModels')} ({chatBoxIds.length}/3)
          </span>
        </header>

        <MultipleChatBox
          chatBoxIds={chatBoxIds}
          controller={controller}
          removeChatBox={removeChatBox}
          addChatBox={addChatBox}
          stopOutputMessage={stopOutputMessage}
          conversation={currentConversation}
        ></MultipleChatBox>
      </section>
    );
  }

  return (
    <RootLayoutContainer>
      <section className="h-full flex flex-col" data-testid="chat-detail">
        {/* One row filling the viewport: the conversation list and the chat box
            are two panes of the same surface, split by a single hairline. The
            chat box used to sit inside a bordered, rounded card above a 36px
            strip, which read as a picture frame floating in the page. */}
        <article className="flex flex-1 min-h-0">
          <Sessions
            handleConversationCardClick={handleConversationCardClick}
            visible={sessionsVisible}
            onVisibleChange={setSessionsVisible}
            onOpenSettings={showSettings}
          ></Sessions>

          <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
            {/* Rendered only while the conversation list is collapsed: an
                expanded list already names the active conversation, and an
                empty header bar would still cost its own height. */}
            {!sessionsVisible && (
              // A fixed-height row: the header can never grow into the
              // transcript, whatever it has to show.
              <header
                className={cn(
                  'flex h-12 shrink-0 flex-row items-center px-4',
                  {
                    'border-b border-cable-hairline': hasSingleChatBox,
                  },
                )}
              >
                <ConversationHeader
                  chatId={chatId}
                  sessionId={conversationId}
                  title={currentConversationName}
                  llmId={currentDialog?.llm_id}
                  onModelChange={handleModelChange}
                  summarizable={isPersistedConversationId(conversationId)}
                  onExpandSessions={handleExpandSessions}
                  onOpenSettings={showSettings}
                ></ConversationHeader>
              </header>
            )}

            <div className="min-h-0 flex-1">
              <SingleChatBox conversation={currentConversation} />
            </div>
          </div>

          <ChatSettings
            visible={settingsVisible}
            onVisibleChange={(nextVisible) =>
              nextVisible ? showSettings() : hideSettings()
            }
            onOpenMultiModel={handleOpenMultiModel}
          ></ChatSettings>
        </article>
      </section>
    </RootLayoutContainer>
  );
}
