'use client';

import { AvatarNameDescription } from '@/components/avatar-name-description';
import { KnowledgeBaseFormField } from '@/components/knowledge-base-item';
import { LlmSettingFieldItems } from '@/components/llm-setting-items/next';
import { prefixName } from '@/utils/form';

type ModelDatasetFieldsProps = {
  prefix?: string;
  /** The embedding page reuses these fields without the assistant identity. */
  hideName?: boolean;
};

/**
 * Assistant identity, chat model with its generation parameters, and the
 * datasets the assistant answers from.
 */
export function ModelDatasetFields({
  prefix = '',
  hideName = false,
}: ModelDatasetFieldsProps) {
  const llmSettingPrefix = prefixName(prefix, 'llm_setting');

  return (
    <div className="space-y-6">
      {hideName || (
        <AvatarNameDescription
          avatarField={prefixName(prefix, 'icon')}
          nameField={prefixName(prefix, 'name')}
          descriptionField={prefixName(prefix, 'description')}
        />
      )}

      <LlmSettingFieldItems
        prefix={llmSettingPrefix}
        llmId={prefixName(prefix, 'llm_id')}
      ></LlmSettingFieldItems>

      <KnowledgeBaseFormField
        name={prefixName(prefix, 'dataset_ids')}
      ></KnowledgeBaseFormField>
    </div>
  );
}
