import { IFlowTemplate } from '@/interfaces/database/agent';
import {
  collectTemplateCategories,
  getTemplateCanvasTypes,
  templateMatchesCategory,
} from './template-categories';

const buildTemplate = (
  overrides: Partial<IFlowTemplate>,
): IFlowTemplate =>
  ({
    id: 'template',
    canvas_type: 'Recommended',
    dsl: {},
    title: { en: '', zh: '', de: '' },
    description: { en: '', zh: '', de: '' },
    ...overrides,
  }) as IFlowTemplate;

describe('template-categories', () => {
  it('prefers canvas_types and ignores non-string entries', () => {
    const template = buildTemplate({
      canvas_types: ['Cable Industry', 1 as unknown as string, 'Recommended'],
    });

    expect(getTemplateCanvasTypes(template)).toEqual([
      'Cable Industry',
      'Recommended',
    ]);
  });

  it('falls back to the legacy canvas_type field', () => {
    const template = buildTemplate({ canvas_types: [], canvas_type: 'Agent' });

    expect(getTemplateCanvasTypes(template)).toEqual(['Agent']);
  });

  it('matches a category case-insensitively', () => {
    const template = buildTemplate({
      canvas_types: ['Cable Industry', 'Recommended'],
    });

    expect(templateMatchesCategory(template, 'cable industry')).toBe(true);
    expect(templateMatchesCategory(template, 'Marketing')).toBe(false);
  });

  it('collects every advertised category once', () => {
    const categories = collectTemplateCategories([
      buildTemplate({ id: 'a', canvas_types: ['Cable Industry', 'Recommended'] }),
      buildTemplate({ id: 'b', canvas_types: ['Recommended'] }),
      buildTemplate({ id: 'c', canvas_types: [], canvas_type: 'Agent' }),
    ]);

    expect(categories).toEqual(['Cable Industry', 'Recommended', 'Agent']);
  });
});
