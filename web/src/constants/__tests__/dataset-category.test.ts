import { IDataset } from '@/interfaces/database/dataset';
import {
  DatasetCategory,
  DatasetCategoryDefinitions,
  DatasetCategoryNavOrder,
  datasetsInNavCategory,
  groupDatasetsByCategory,
  resolveDatasetCategory,
} from '../dataset-category';

const dataset = (
  name: string,
  extra: { description?: string; category?: string } = {},
) =>
  ({
    id: name,
    name,
    document_count: 0,
    ...extra,
  }) as Pick<IDataset, 'name' | 'description'> & { category?: string };

describe('resolveDatasetCategory', () => {
  it.each([
    ['BOM 结构库', DatasetCategory.Bom],
    ['线缆截面配方', DatasetCategory.Bom],
    ['GB/T 标准规范', DatasetCategory.Standard],
    ['IEC 60228 国标合集', DatasetCategory.Standard],
    ['护套材料技术规格书', DatasetCategory.Spec],
    ['Cable_Tech_Docs', DatasetCategory.Spec],
    ['出厂质检规则', DatasetCategory.Quality],
    ['合规审计底稿', DatasetCategory.Quality],
    ['公司年报', DatasetCategory.General],
  ])('classifies %s as %s from its name', (name, expected) => {
    expect(resolveDatasetCategory(dataset(name)).category).toBe(expected);
  });

  it('matches the description when the name says nothing', () => {
    expect(
      resolveDatasetCategory(dataset('Docs', { description: 'GB/T 标准原文' }))
        .category,
    ).toBe(DatasetCategory.Standard);
  });

  it.each([
    ['logbook', DatasetCategory.General],
    ['bombardier', DatasetCategory.General],
    ['reimbursement', DatasetCategory.General],
  ])('does not read a keyword out of %s', (name, expected) => {
    // 'gb' inside 'logbook' and 'bom' inside 'bombardier' are the reason ASCII
    // needles match on a word boundary rather than as substrings.
    expect(resolveDatasetCategory(dataset(name)).category).toBe(expected);
  });

  it('prefers a declared category over the name', () => {
    expect(
      resolveDatasetCategory(dataset('随便起的名字', { category: 'bom' })).category,
    ).toBe(DatasetCategory.Bom);
  });

  it('accepts a declared label as well as a key', () => {
    expect(
      resolveDatasetCategory(dataset('Docs', { category: 'GB/T 标准规范' }))
        .category,
    ).toBe(DatasetCategory.Standard);
  });

  it.each(['通用/其他', 'general', '默认', '其他'])(
    'reads the declared class %s as the general bucket, not a custom tag',
    (category) => {
      const resolution = resolveDatasetCategory(dataset('Docs', { category }));

      expect(resolution.category).toBe(DatasetCategory.General);
      expect(resolution.customTag).toBeUndefined();
    },
  );

  it('keeps an unrecognised declared tag as the custom class', () => {
    const resolution = resolveDatasetCategory(
      dataset('Docs', { category: '我的分类' }),
    );

    expect(resolution.category).toBe(DatasetCategory.Custom);
    expect(resolution.customTag).toBe('我的分类');
  });

  it('ignores a blank declared category', () => {
    expect(
      resolveDatasetCategory(dataset('GB/T 标准规范', { category: '  ' }))
        .category,
    ).toBe(DatasetCategory.Standard);
  });
});

describe('dataset categories', () => {
  it('defines an icon, a tone and a chip label for every class', () => {
    Object.values(DatasetCategory).forEach((category) => {
      const definition = DatasetCategoryDefinitions[category];

      expect(definition).toBeDefined();
      expect(definition.icon).toBeDefined();
      expect(definition.toneClass).toMatch(/^category-tone-/);
      expect(definition.chipKey).toMatch(/^datasetCategory\./);
    });
  });

  it('lists five navigation classes and keeps the custom class out of them', () => {
    expect(DatasetCategoryNavOrder).toHaveLength(5);
    expect(DatasetCategoryNavOrder).not.toContain(DatasetCategory.Custom);
  });

  it('groups knowledge bases, then folds the custom ones into the general bucket', () => {
    const groups = groupDatasetsByCategory([
      dataset('BOM 结构库'),
      dataset('GB/T 标准规范'),
      dataset('Docs', { category: '我的分类' }),
      dataset('公司年报'),
    ] as IDataset[]);

    expect(groups[DatasetCategory.Bom]).toHaveLength(1);
    expect(groups[DatasetCategory.Standard]).toHaveLength(1);
    expect(groups[DatasetCategory.Custom]).toHaveLength(1);
    expect(groups[DatasetCategory.General]).toHaveLength(1);

    expect(datasetsInNavCategory(groups, DatasetCategory.General)).toHaveLength(
      2,
    );
    expect(datasetsInNavCategory(groups, DatasetCategory.Bom)).toHaveLength(1);
  });
});
