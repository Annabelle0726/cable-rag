import { MessageType } from '@/constants/chat';
import { useTranslate } from '@/hooks/common-hooks';
import {
  useFetchChatList,
  useFetchSessionList,
  useGetChatSearchParams,
} from '@/hooks/use-chat-request';
import { IConversation } from '@/interfaces/database/chat';
import { generateTemporaryConversationId } from '@/utils/chat';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { useChatUrlParams } from './use-chat-url';

export const useFindPrologueFromDialogList = () => {
  const { id: dialogId } = useParams();
  const { data } = useFetchChatList();

  const prologue = useMemo(() => {
    return data?.chats.find((x) => x.id === dialogId)?.prompt_config?.prologue;
  }, [dialogId, data]);

  return prologue;
};

export const useSelectDerivedConversationList = () => {
  const { t } = useTranslate('chat');

  const [list, setList] = useState<Array<IConversation>>([]);
  const {
    data: conversationList,
    loading,
    handleInputChange,
    searchString,
    setSearchString,
  } = useFetchSessionList();

  const { id: dialogId } = useParams();
  const prologue = useFindPrologueFromDialogList();
  const { setConversationBoth } = useChatUrlParams();
  const { conversationId, isNew } = useGetChatSearchParams();

  const addTemporaryConversation = useCallback(() => {
    if (!dialogId) {
      return;
    }
    // Clear the search keyword, otherwise the newly created session will be
    // filtered out by the search after it is persisted and refetched.
    setSearchString('');
    // Open the placeholder conversation, so its prologue shows and the list
    // highlights the row. The id is marked temporary, which keeps every session
    // request away from the server until the first send creates the real one.
    //
    // Write the route BEFORE touching state: writing it from inside a state
    // updater let React defer or re-run the update and left the previous
    // conversationId in the query string, so the page requested a session that
    // does not exist (`102 Session not found`).
    const conversationId = generateTemporaryConversationId();
    setConversationBoth(conversationId, 'true');

    setList((previous) => [
      {
        id: conversationId,
        name: t('newConversation'),
        chat_id: dialogId,
        is_new: true,
        messages: [
          {
            content: prologue,
            role: MessageType.Assistant,
          },
        ],
      } as any,
      ...previous,
    ]);
  }, [
    dialogId,
    setConversationBoth,
    t,
    prologue,
    setSearchString,
  ]);

  const removeTemporaryConversation = useCallback((conversationId: string) => {
    setList((prevList) => {
      return prevList.filter(
        (conversation) => conversation.id !== conversationId,
      );
    });
  }, []);

  // When you first enter the page, select the top conversation card

  // useEffect(() => {
  //   setList((prevList) => {
  //     const tempItems = prevList.filter((item) => item.is_new);
  //     const existingTempIds = new Set(tempItems.map((t) => t.id));
  //     const newItems = conversationList.filter(
  //       (item) => !existingTempIds.has(item.id),
  //     );
  //     return [...tempItems, ...newItems];
  //   });
  // }, [conversationList]);

  useEffect(() => {
    setList([...conversationList]);
  }, [conversationList]);

  /**
   * Opening a chat without a conversation — a card click lands on `/chat/{id}`,
   * with no query string — used to leave the chat pane blank until the user
   * picked a row. Fall back to the first conversation of the list, which the
   * endpoint has already ordered by pin and activity, so the newest conversation
   * is what opens.
   *
   * A conversation already named in the URL is left alone, and so is a
   * placeholder the user just started: writing either of those would fight the
   * user's own choice, or reopen a placeholder under its temporary id.
   */
  useEffect(() => {
    if (conversationId || isNew === 'true') return;

    const firstConversation = conversationList[0];
    if (!firstConversation) return;

    setConversationBoth(firstConversation.id, '');
  }, [conversationId, isNew, conversationList, setConversationBoth]);

  return {
    list,
    addTemporaryConversation,
    removeTemporaryConversation,
    loading,
    handleInputChange,
    searchString,
  };
};
