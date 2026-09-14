import { Button } from '@/components/ui/button';
import { Form } from '@/components/ui/form';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { DatasetMetadata } from '@/constants/chat';
import { useSetModalState } from '@/hooks/common-hooks';
import { useFetchChat, useUpdateChat } from '@/hooks/use-chat-request';
import { useFindLlmByUuid } from '@/hooks/use-llm-request';
import {
  useRevalidateStaleDatasetIds,
  useStaleDatasetFormSchema,
} from '@/hooks/use-stale-dataset-validation';
import {
  removeUselessFieldsFromValues,
  setLLMSettingEnabledValues,
} from '@/utils/form';
import { zodResolver } from '@hookform/resolvers/zod';
import { isEmpty, omit } from 'lodash';
import { LucideSettings } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';
import { z } from 'zod';
import { getWebSearchProvider } from '../web-search-api-key';
import { ModelDatasetFields } from './sections/model-dataset-fields';
import { PrologueFields } from './sections/prologue-fields';
import { RetrievalFields } from './sections/retrieval-fields';
import { SystemPromptFields } from './sections/system-prompt-fields';
import { SavingButton } from './saving-button';
import { SettingsDrawer } from './settings-drawer';
import { useChatSettingSchema } from './use-chat-setting-schema';
import { useRevealSubmitErrors } from './use-reveal-submit-errors';

type ChatSettingsProps = { hasSingleChatBox: boolean };

/** The drawer's accordion sections; the first one is open when it slides in. */
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

export function ChatSettings({ hasSingleChatBox }: ChatSettingsProps) {
  const { data } = useFetchChat();

  const chatSettingSchema = useChatSettingSchema();
  const { formSchema, datasetsFetched } = useStaleDatasetFormSchema(
    chatSettingSchema,
    data?.dataset_ids,
  );
  const { updateChat, loading } = useUpdateChat();
  const findLlmByUuid = useFindLlmByUuid();
  const { id } = useParams();
  const { t } = useTranslation();

  const { visible: settingVisible, switchVisible: switchSettingVisible } =
    useSetModalState(false);

  const {
    formContainerRef,
    handleInvalidSubmit,
    openSections,
    onOpenSectionsChange,
  } = useRevealSubmitErrors(SettingsSections, [RetrievalSection]);

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

  async function onSubmit(values: FormSchemaType) {
    const nextValues: Record<string, any> = removeUselessFieldsFromValues(
      values,
      'llm_setting.',
    );
    const referenceMetadata = nextValues?.prompt_config?.reference_metadata;
    if (
      referenceMetadata &&
      Array.isArray(referenceMetadata.fields) &&
      referenceMetadata.fields.length === 0
    ) {
      referenceMetadata.fields = undefined;
    }

    // Add model_type to llm_setting based on the selected llm_id
    if (nextValues.llm_id) {
      nextValues.llm_setting = {
        ...nextValues.llm_setting,
        model_type: findLlmByUuid(nextValues.llm_id)?.model_type || 'chat',
      };
    }

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
        ...nextValues,
      },
    });
  }

  useEffect(() => {
    const llmSettingEnabledValues = setLLMSettingEnabledValues(
      data.llm_setting,
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
      prompt_config: {
        ...data.prompt_config,
        // reset() skips undefined values, so fall back to '' to clear the field
        web_search_provider: getWebSearchProvider(data.prompt_config) ?? '',
        reference_metadata: normalizedReferenceMetadata,
      },
      ...llmSettingEnabledValues,
    };

    if (!isEmpty(data)) {
      form.reset(nextData as FormSchemaType);
    }
  }, [data, form]);

  useRevalidateStaleDatasetIds(form, datasetsFetched);

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
      content: <ModelDatasetFields />,
    },
  ];

  return (
    <>
      {settingVisible || (
        <div className="flex shrink-0 items-start pt-3 pr-3">
          <Button
            onClick={switchSettingVisible}
            disabled={!hasSingleChatBox}
            variant="ghost"
            size="icon-sm"
            className="rounded-lg text-text-secondary hover:bg-cable-brand-soft hover:text-cable-brand"
            aria-label={t('chat.chatSetting')}
            title={t('chat.chatSetting')}
            data-testid="chat-settings"
          >
            <LucideSettings className="size-4" />
          </Button>
        </div>
      )}

      <SettingsDrawer
        open={settingVisible}
        onOpenChange={switchSettingVisible}
        title={t('chat.chatSetting')}
        footer={
          <div className="flex items-center justify-end gap-3">
            <Button
              variant={'outline'}
              onClick={switchSettingVisible}
              data-testid="chat-detail-settings-cancel"
            >
              {t('chat.cancel')}
            </Button>
            <SavingButton loading={loading} form={SettingsFormId}></SavingButton>
          </div>
        }
      >
        <Form {...form}>
          <form
            ref={formContainerRef}
            id={SettingsFormId}
            onSubmit={form.handleSubmit(onSubmit, handleInvalidSubmit)}
          >
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
                  className="rounded-xl border border-cable-border px-4 data-[state=open]:bg-cable-surface-muted"
                  data-testid={`chat-settings-section-${section.value}`}
                >
                  <AccordionTrigger className="text-sm font-medium text-text-primary hover:no-underline">
                    {section.title}
                  </AccordionTrigger>
                  <AccordionContent>{section.content}</AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </form>
        </Form>
      </SettingsDrawer>
    </>
  );
}
