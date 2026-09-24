import { SettingsDrawer } from '@/components/settings-drawer';
import { Button } from '@/components/ui/button';
import { Form } from '@/components/ui/form';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { DatasetMetadata } from '@/constants/chat';
import { useFetchChat, useUpdateChat } from '@/hooks/use-chat-request';
import { useFindLlmByUuid } from '@/hooks/use-llm-request';
import {
  useRevalidateStaleDatasetIds,
  useStaleDatasetFormSchema,
} from '@/hooks/use-stale-dataset-validation';
import { isPersistedConversationId } from '@/utils/chat';
import {
  removeUselessFieldsFromValues,
  setLLMSettingEnabledValues,
} from '@/utils/form';
import { zodResolver } from '@hookform/resolvers/zod';
import { isEmpty, omit } from 'lodash';
import { useCallback, useEffect, useLayoutEffect } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';
import { z } from 'zod';
import { useSessionDatasets } from '../../hooks/use-session-datasets';
import { resolveDatasetBinding } from '../../utils';
import { getWebSearchProvider } from '../web-search-api-key';
import { ModelDatasetFields } from './sections/model-dataset-fields';
import { PrologueFields } from './sections/prologue-fields';
import { RetrievalFields } from './sections/retrieval-fields';
import { SystemPromptFields } from './sections/system-prompt-fields';
import { SavingButton } from './saving-button';
import { useChatSettingSchema } from './use-chat-setting-schema';
import { useRevealSubmitErrors } from './use-reveal-submit-errors';

type ChatSettingsProps = {
  /** Open state of the drawer. The chat page owns it so every trigger shares it. */
  visible: boolean;
  onVisibleChange: (visible: boolean) => void;
  /** Enters the multi-model comparison view from the model section. */
  onOpenMultiModel?: () => void;
  /**
   * The open conversation, when the server knows it. Empty for one that only
   * exists in the browser: that conversation is created by this drawer's save,
   * so the binding is on the row before the first question is retrieved from.
   */
  sessionId?: string;
  /**
   * The datasets the open conversation retrieves from — its own binding when it
   * has one, otherwise the assistant's set. The dataset field opens on this set,
   * and an empty one is what the drawer prompts about.
   */
  effectiveDatasetIds?: string[];
  /**
   * The assistant's own set. Confirming it unchanged stores no binding on the
   * conversation, which keeps it following the assistant — later edits to the
   * assistant's datasets included.
   */
  assistantDatasetIds?: string[];
};

/** The drawer's accordion sections. Which one comes up is decided on opening. */
const RetrievalSection = 'retrieval';
const SystemSection = 'system';
const PrologueSection = 'prologue';
const ModelSection = 'model';

const SettingsSections = [
  RetrievalSection,
  SystemSection,
  PrologueSection,
  ModelSection,
] as const;

const SettingsFormId = 'chat-settings-form';

export function ChatSettings({
  visible,
  onVisibleChange,
  onOpenMultiModel,
  sessionId,
  effectiveDatasetIds = [],
  assistantDatasetIds = [],
}: ChatSettingsProps) {
  const { data } = useFetchChat();

  const chatSettingSchema = useChatSettingSchema();
  // The ids the field opens on are the conversation's effective ones, which is
  // also what this lookup has to validate: a conversation can be bound to a
  // dataset the assistant's own set never named.
  const { formSchema, datasetsFetched } = useStaleDatasetFormSchema(
    chatSettingSchema,
    effectiveDatasetIds,
  );
  const { updateChat, loading } = useUpdateChat();
  const {
    createSessionWithDatasets,
    bindSessionDatasets,
    loading: bindingDatasets,
  } = useSessionDatasets();
  const findLlmByUuid = useFindLlmByUuid();
  const { id } = useParams();
  const { t } = useTranslation();

  const closeSettings = useCallback(() => {
    onVisibleChange(false);
  }, [onVisibleChange]);

  const {
    formContainerRef,
    handleInvalidSubmit,
    openSections,
    onOpenSectionsChange,
  } = useRevealSubmitErrors(SettingsSections);

  type FormSchemaType = z.infer<typeof formSchema>;

  const form = useForm<FormSchemaType>({
    resolver: zodResolver(formSchema),
    shouldUnregister: false,
    mode: 'onChange',
    defaultValues: {
      name: '',
      icon: '',
      description: '',
      dataset_ids: [],
      prompt_config: {
        quote: true,
        keyword: false,
        tts: false,
        refine_multiturn: true,
        system: '',
        parameters: [],
        reasoning: false,
        cross_languages: [],
        reference_metadata: {
          include: false,
          fields: undefined,
        },
      },
      top_n: 6,
      rerank_candidates_count: 64,
      similarity_threshold: 0.25,
      vector_similarity_weight: 0.3,
      meta_data_filter: {
        method: DatasetMetadata.Disabled,
        manual: [],
      },
    },
  });

  /**
   * Writes the confirmed selection onto the open conversation.
   *
   * A conversation the server knows is rebound; one that only exists in the
   * browser has no row to patch, so it is created here with the binding already
   * on it — before the first question, which is when retrieval needs it. A
   * selection identical to the assistant's own set is stored as no binding at
   * all, so the conversation keeps inheriting the assistant's set.
   */
  const saveDatasetSelection = useCallback(
    async (selectedDatasetIds: string[]) => {
      const datasetIds = resolveDatasetBinding(
        selectedDatasetIds,
        assistantDatasetIds,
      );

      if (isPersistedConversationId(sessionId)) {
        await bindSessionDatasets({ sessionId, datasetIds });
        return;
      }

      await createSessionWithDatasets({
        name: t('chat.newConversation'),
        datasetIds,
      });
    },
    [
      assistantDatasetIds,
      bindSessionDatasets,
      createSessionWithDatasets,
      sessionId,
      t,
    ],
  );

  async function onSubmit(values: FormSchemaType) {
    const nextValues: Record<string, any> = removeUselessFieldsFromValues(
      values,
      'llm_setting.',
    );
    // The dataset field edits the open conversation, not the assistant: its
    // `dataset_ids` leaves the assistant payload here and is written as the
    // conversation's own binding below. Every other setting in this drawer still
    // saves to the assistant, exactly as it did before.
    const { dataset_ids: selectedDatasetIds, ...assistantValues } = nextValues;
    const referenceMetadata =
      assistantValues?.prompt_config?.reference_metadata;
    if (
      referenceMetadata &&
      Array.isArray(referenceMetadata.fields) &&
      referenceMetadata.fields.length === 0
    ) {
      referenceMetadata.fields = undefined;
    }

    // Add model_type to llm_setting based on the selected llm_id
    if (assistantValues.llm_id) {
      assistantValues.llm_setting = {
        ...assistantValues.llm_setting,
        model_type: findLlmByUuid(assistantValues.llm_id)?.model_type || 'chat',
      };
    }

    // The binding first: a conversation that does not exist yet is created by
    // it, and the question that follows must find the datasets already there.
    await saveDatasetSelection(selectedDatasetIds ?? []);

    updateChat({
      chatId: id!,
      params: {
        ...omit(data, [
          'operator_permission',
          'tenant_id',
          'tenant_llm_id',
          'tenant_rerank_id',
          'created_by',
          'create_time',
          'create_date',
          'update_time',
          'update_date',
          'id',
          'top_k',
        ]),
        ...assistantValues,
      },
    });
  }

  /**
   * The effective set as one value. The page rebuilds that array on every
   * session-list refetch, and re-seeding the form from an equal set would throw
   * away edits the user has not saved yet — so the seeding keys on the contents
   * rather than on the array.
   */
  const effectiveDatasetIdsKey = effectiveDatasetIds.join(',');

  useEffect(() => {
    const llmSettingEnabledValues = setLLMSettingEnabledValues(
      data?.llm_setting,
    );
    const referenceMetadata = data?.prompt_config?.reference_metadata;
    const normalizedReferenceMetadata =
      referenceMetadata &&
      Array.isArray(referenceMetadata.fields) &&
      referenceMetadata.fields.length === 0
        ? { ...referenceMetadata, fields: undefined }
        : referenceMetadata;

    const nextData = {
      ...omit(data, 'top_k'),
      // The field edits the open conversation, so it opens on that
      // conversation's effective set rather than on the assistant's own.
      dataset_ids: effectiveDatasetIdsKey
        ? effectiveDatasetIdsKey.split(',')
        : [],
      prompt_config: {
        ...data?.prompt_config,
        // reset() skips undefined values, so fall back to '' to clear the field
        web_search_provider: getWebSearchProvider(data?.prompt_config) ?? '',
        reference_metadata: normalizedReferenceMetadata,
      },
      ...llmSettingEnabledValues,
    };

    if (!isEmpty(data)) {
      form.reset(nextData as FormSchemaType);
    }
  }, [data, form, effectiveDatasetIdsKey]);

  useRevalidateStaleDatasetIds(form, datasetsFetched);

  /** The selection the drawer is showing, which is what the notice is about. */
  const selectedDatasetIds = useWatch({
    control: form.control,
    name: 'dataset_ids',
  }) as string[] | undefined;

  /**
   * A conversation with nothing selected answers from nothing, so the drawer
   * says so and puts the field that fixes it in front of the user.
   */
  const hasNoDatasetSelected = isEmpty(selectedDatasetIds);

  /**
   * The drawer reveals the model & dataset section — the one holding the field
   * the notice above the accordion is about — while the conversation has nothing
   * to retrieve from, and keeps the retrieval settings first otherwise.
   *
   * Decided on the opening edge and read from the form at that moment, never
   * re-applied while the panel is open: a selection made in the field must not
   * collapse the section the user is working in.
   */
  useLayoutEffect(() => {
    if (!visible) return;

    const openingSelection = form.getValues('dataset_ids') ?? [];
    onOpenSectionsChange(
      openingSelection.length === 0 ? [ModelSection] : [RetrievalSection],
    );
  }, [visible, form, onOpenSectionsChange]);

  const sections = [
    {
      value: RetrievalSection,
      title: t('chat.retrievalSettings'),
      content: <RetrievalFields />,
    },
    {
      value: SystemSection,
      title: t('chat.roleAndPrompt'),
      content: <SystemPromptFields />,
    },
    {
      value: PrologueSection,
      title: t('chat.prologueAndFallback'),
      content: <PrologueFields />,
    },
    {
      value: ModelSection,
      title: t('chat.modelAndDataset'),
      content: <ModelDatasetFields onOpenMultiModel={onOpenMultiModel} />,
    },
  ];

  return (
    <SettingsDrawer
      open={visible}
      onOpenChange={onVisibleChange}
      title={t('chat.chatSetting')}
      testId="chat-detail-settings"
      footer={
        <div className="flex items-center justify-end gap-3">
          <Button
            variant={'outline'}
            onClick={closeSettings}
            data-testid="chat-detail-settings-cancel"
          >
            {t('chat.cancel')}
          </Button>
          <SavingButton
            loading={loading || bindingDatasets}
            form={SettingsFormId}
          ></SavingButton>
        </div>
      }
    >
      <Form {...form}>
        <form
          ref={formContainerRef}
          id={SettingsFormId}
          onSubmit={form.handleSubmit(onSubmit, handleInvalidSubmit)}
        >
          {/* The prompt a new conversation is opened with: nothing is selected,
              so there is nothing to retrieve an answer from until the field in
              the model & dataset section below is filled in. */}
          {hasNoDatasetSelected && (
            <p
              role="status"
              className="mb-4 rounded-xl border border-cable-border bg-cable-surface-muted p-3 text-sm text-text-secondary"
              data-testid="chat-settings-no-dataset"
            >
              {t('chat.datasetNotSelectedNotice')}
            </p>
          )}

          <Accordion
            type="multiple"
            value={openSections}
            onValueChange={onOpenSectionsChange}
            className="space-y-2"
          >
            {sections.map((section) => (
              <AccordionItem
                key={section.value}
                value={section.value}
                className="rounded-xl border border-cable-border px-4 data-[state=open]:bg-cable-surface-muted last:border-b last:border-cable-border"
              >
                <AccordionTrigger
                  className="text-sm font-medium text-text-primary hover:no-underline"
                  data-testid={`chat-settings-section-${section.value}`}
                >
                  {section.title}
                </AccordionTrigger>
                <AccordionContent>{section.content}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
          <div
            className="h-10 shrink-0 pointer-events-none"
            aria-hidden="true"
          />
        </form>
      </Form>
    </SettingsDrawer>
  );
}
