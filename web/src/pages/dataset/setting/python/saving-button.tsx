import { ButtonLoading } from '@/components/ui/button';
import { PermissionRole } from '@/constants/permission';
import { ParseType } from '@/constants/knowledge';
import {
  useUpdateDatasetAuthorization,
  useUpdateKnowledge,
} from '@/hooks/use-knowledge-request';
import { useMemo } from 'react';
import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

export function GeneralSavingButton() {
  const form = useFormContext();
  const { saveKnowledgeConfiguration, loading: submitLoading } =
    useUpdateKnowledge();
  const { id: kb_id } = useParams();
  const { t } = useTranslation();

  const defaultValues = useMemo(
    () => form.formState.defaultValues ?? {},
    [form.formState.defaultValues],
  );
  const chunk_method = defaultValues['chunk_method'];

  return (
    <ButtonLoading
      type="button"
      loading={submitLoading}
      data-testid="ds-settings-basic-save-btn"
      onClick={() => {
        (async () => {
          const isValidate = await form.trigger('name');
          const { name, description, permission, avatar } = form.getValues();

          if (isValidate) {
            saveKnowledgeConfiguration({
              kb_id,
              chunk_method,
              name,
              description,
              avatar,
              permission,
            });
          }
        })();
      }}
    >
      {t('knowledgeConfiguration.save')}
    </ButtonLoading>
  );
}

export function SavingButton() {
  const { saveKnowledgeConfiguration, loading: submitLoading } =
    useUpdateKnowledge();
  const { saveDatasetAuthorization } = useUpdateDatasetAuthorization();
  const form = useFormContext();
  const { id: kb_id } = useParams();
  const { t } = useTranslation();

  return (
    <ButtonLoading
      loading={submitLoading}
      data-testid="ds-settings-page-save-btn"
      onClick={() => {
        (async () => {
          try {
            const beValid = await form.trigger();
            if (!beValid) {
              const errors = form.formState.errors;
              console.error('Validation errors:', errors);
            }
            if (beValid) {
              form.handleSubmit(async (originalValues) => {
                const values = originalValues;
                if (originalValues.parse_type === ParseType.BuiltIn) {
                  values.pipeline_id = null;
                } else {
                  values.chunk_method = null;
                }

                await saveKnowledgeConfiguration({
                  kb_id,
                  ...values,
                  parser_config: {
                    ...values.parser_config,
                    image_table_context_window:
                      values.parser_config.image_table_context_window,
                    image_context_size:
                      values.parser_config.image_table_context_window,
                    table_context_size:
                      values.parser_config.image_table_context_window,
                    // Unset children delimiter if this option is not enabled
                    children_delimiter: values.parser_config.enable_children
                      ? values.parser_config.children_delimiter
                      : '',
                  },
                });

                // The mode is stored on the dataset row, but its subjects live in
                // the authorization table, so the grant is written by its own
                // endpoint — which also clears the subjects for a mode that has
                // none, leaving no stale grants behind.
                await saveDatasetAuthorization({
                  datasetId: kb_id as string,
                  permission: values.permission,
                  department_ids:
                    values.permission === PermissionRole.Custom
                      ? (values.department_ids ?? [])
                      : [],
                  user_ids:
                    values.permission === PermissionRole.Custom
                      ? (values.user_ids ?? [])
                      : [],
                });
              })();
            }
          } catch (e) {
            console.log(e);
          }
        })();
      }}
    >
      {t('knowledgeConfiguration.save')}
    </ButtonLoading>
  );
}
