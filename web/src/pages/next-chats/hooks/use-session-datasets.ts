import { useCreateSession, useUpdateSession } from '@/hooks/use-chat-request';
import notification from '@/utils/notification';
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';
import { useChatUrlParams } from './use-chat-url';

type SessionDatasetBinding = {
  /** The datasets to bind to, or `null` to inherit the assistant's set. */
  datasetIds: string[] | null;
};

/**
 * The two ways a conversation's dataset binding reaches the server: creating
 * the conversation with one, and rebinding the open one.
 *
 * Both take the `dataset_ids` the settings drawer's dataset field resolved —
 * `null` means "this conversation inherits the assistant's set", which is what
 * the server stores when the user confirms without changing anything.
 */
export const useSessionDatasets = () => {
  const { id: chatId } = useParams();
  const { t } = useTranslation();
  const { createSession, loading: creating } = useCreateSession();
  const { updateSession, loading: updating } = useUpdateSession();
  const { setConversationBoth } = useChatUrlParams();

  /**
   * Creates the conversation the settings drawer was opened on and opens it, so
   * the datasets are bound before the first question is asked.
   */
  const createSessionWithDatasets = useCallback(
    async ({
      name,
      datasetIds,
    }: SessionDatasetBinding & { name: string }): Promise<string> => {
      if (!chatId) {
        return '';
      }

      const data = await createSession({
        chatId,
        name,
        datasetIds: datasetIds ?? undefined,
      }).catch(() => undefined);

      const createdSessionId = data?.code === 0 ? (data?.data?.id ?? '') : '';
      if (!createdSessionId) {
        // Nothing was bound, so say why rather than dropping the selection.
        notification.error({ message: t('chat.createSessionFailed') });
        return '';
      }

      setConversationBoth(createdSessionId, '');
      return createdSessionId;
    },
    [chatId, createSession, setConversationBoth, t],
  );

  /** Rebinds an existing conversation; `datasetIds: null` restores inheritance. */
  const bindSessionDatasets = useCallback(
    async ({
      sessionId,
      datasetIds,
    }: SessionDatasetBinding & { sessionId: string }): Promise<boolean> => {
      if (!chatId || !sessionId) {
        return false;
      }

      const data = await updateSession({
        chatId,
        sessionId,
        params: { dataset_ids: datasetIds },
      }).catch(() => undefined);

      return data?.code === 0;
    },
    [chatId, updateSession],
  );

  return {
    createSessionWithDatasets,
    bindSessionDatasets,
    loading: creating || updating,
  };
};
