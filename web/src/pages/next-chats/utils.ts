import { NextMessageInputOnPressEnterParameter } from '@/components/message-input/next';
import { EmptyConversationId } from '@/constants/chat';
import { IConversation, IReference } from '@/interfaces/database/chat';
import storage from '@/utils/authorization-util';
import { isEqual } from 'lodash';

/**
 * Regenerate is triggered from the transcript, which has no access to the input
 * box's thinking / internet toggles, so callers replay the options of their last
 * send. A view that hasn't sent anything yet has no record: fall back to the
 * input box's own defaults — it re-reads the persisted thinking level and starts
 * with internet off, so both stay in sync after a remount.
 */
export function resolveResendOptions(
  lastSendOptions: NextMessageInputOnPressEnterParameter,
): NextMessageInputOnPressEnterParameter {
  const {
    enableThinking = storage.getThinkingLevel(),
    enableInternet = false,
  } = lastSendOptions;

  return { enableThinking, enableInternet };
}

export const isConversationIdExist = (conversationId: string) => {
  return conversationId !== EmptyConversationId && conversationId !== '';
};

/**
 * The `dataset_ids` a conversation should carry for the selection the dataset
 * drawer confirmed.
 *
 * A session stores an array when it has a binding of its own and `null` when it
 * inherits the assistant's set. Confirming the set the drawer opened with is
 * therefore not a binding but the absence of one: it is stored as `null`, so the
 * conversation keeps following the assistant — including edits made to the
 * assistant afterwards. Anything else is an explicit binding, empty included
 * (a conversation that retrieves from nothing is a decision, not an omission).
 */
export function resolveDatasetBinding(
  selectedDatasetIds: string[],
  assistantDatasetIds: string[],
): string[] | null {
  const isSameSelection = isEqual(
    [...selectedDatasetIds].sort(),
    [...assistantDatasetIds].sort(),
  );

  return isSameSelection ? null : [...selectedDatasetIds];
}

export const getDocumentIdsFromConversionReference = (data: IConversation) => {
  const documentIds = data.reference.reduce(
    (pre: Array<string>, cur: IReference) => {
      cur.doc_aggs
        ?.map((x) => x.doc_id)
        .forEach((x) => {
          if (pre.every((y) => y !== x)) {
            pre.push(x);
          }
        });
      return pre;
    },
    [],
  );
  return documentIds.join(',');
};

// Shared fallback so a message without a reference keeps handing MessageItem the
// same object across renders. A fresh literal here would break the item's memo
// on every streaming flush. See useMessageReferences.
export const EmptyReference: IReference = {
  doc_aggs: [],
  chunks: [],
  total: 0,
};
