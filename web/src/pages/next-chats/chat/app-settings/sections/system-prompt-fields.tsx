'use client';

import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Textarea } from '@/components/ui/textarea';
import { prefixName } from '@/utils/form';
import { getDirAttribute } from '@/utils/text-direction';
import { useCallback, useEffect, useRef } from 'react';
import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { DynamicVariableForm } from '../dynamic-variable';

type SystemPromptFieldsProps = { prefix?: string };

/** Minimum height of the prompt box: roughly the cable prompt's first screen. */
const SystemPromptMinHeight = 'min-h-[10rem]';

/**
 * The assistant's role: the system prompt (with its `{knowledge}` slot) and the
 * variables it may reference.
 *
 * The prompt is long by nature, so the textarea grows with its content up to a
 * share of the viewport instead of scrolling inside a small box; past that it
 * scrolls, and it can still be dragged taller by hand.
 */
export function SystemPromptFields({ prefix = '' }: SystemPromptFieldsProps) {
  const { t } = useTranslation();
  const form = useFormContext();
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const systemPromptValue = form.watch(
    prefixName(prefix, 'prompt_config.system'),
  );

  const resizeToContent = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    // Reset first: the scroll height of a box that is already tall would only
    // ever grow, so shrinking the prompt could never shorten the box.
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, []);

  useEffect(() => {
    resizeToContent();
  }, [resizeToContent, systemPromptValue]);

  return (
    <div className="space-y-6">
      <FormField
        control={form.control}
        name={prefixName(prefix, 'prompt_config.system')}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{t('chat.system')}</FormLabel>
            <FormControl>
              <Textarea
                {...field}
                ref={(element: HTMLTextAreaElement | null) => {
                  textareaRef.current = element;
                  field.ref(element);
                }}
                rows={8}
                className={`${SystemPromptMinHeight} max-h-[45vh] resize-y overflow-y-auto`}
                placeholder={t('chat.systemPlaceholder')}
                dir={getDirAttribute(systemPromptValue || '')}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <DynamicVariableForm
        name={prefixName(prefix, 'prompt_config.parameters')}
      ></DynamicVariableForm>
    </div>
  );
}
