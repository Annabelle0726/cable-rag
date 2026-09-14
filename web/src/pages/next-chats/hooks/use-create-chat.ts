import { useSetModalState } from '@/hooks/common-hooks';
import { useCreateChat } from '@/hooks/use-chat-request';
import { useFetchDefaultModelDictionary } from '@/hooks/use-llm-request';
import { useCallback, useMemo } from 'react';

export const useCreateChatDialog = () => {
  const {
    visible: createChatVisible,
    hideModal: hideCreateChatModal,
    showModal: showCreateChatModal,
  } = useSetModalState();
  const { createChat, loading: createLoading } = useCreateChat();
  const defaultModelDictionary =
    useFetchDefaultModelDictionary(createChatVisible);

  const InitialData = useMemo(
    () => ({
      name: '',
      icon: '',
      language: 'English',
      description: '',
      dataset_ids: [],
      // The prompt and retrieval defaults (system prompt, opener, no-result
      // answer, similarity threshold, vector weight, top N, rerank candidates)
      // belong to the backend, which applies the cable vertical values in
      // api/db/cable_defaults.py. Sending them from here would override those
      // defaults with a second copy that has to be kept in step.
      prompt_config: {
        quote: true,
        keyword: false,
        tts: false,
        refine_multiturn: false,
        use_kg: false,
        reasoning: false,
        parameters: [
          { key: 'knowledge', optional: false },
          { key: 'date', optional: true },
        ],
        toc_enhance: false,
      },
      llm_id: defaultModelDictionary?.llm_id,
      tenant_llm_id: defaultModelDictionary?.llm_id,
      llm_setting: {},
    }),
    [defaultModelDictionary?.llm_id],
  );

  const onCreateChatOk = useCallback(
    async (name: string) => {
      const ret = await createChat({ ...InitialData, name });
      if (ret === 0) {
        hideCreateChatModal();
      }
    },
    [InitialData, createChat, hideCreateChatModal],
  );

  return {
    createChatLoading: createLoading,
    onCreateChatOk,
    createChatVisible,
    hideCreateChatModal,
    showCreateChatModal,
  };
};
