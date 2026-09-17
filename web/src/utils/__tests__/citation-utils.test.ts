import { citedChunkIndex, parseCitationIndex } from '@/utils/citation-utils';

// Two numbering bases coexist in this product, and mixing them is what produced
// a phantom "图 6" with no image:
//   - chat / agentic answers cite 1-based block labels ("ID: 1" … "ID: n", from
//     kb_prompt), so a marker must be shifted into a 0-based pool index;
//   - the search/ask flow already emits 0-based markers (insert_citations).
describe('citation index basis', () => {
  describe('parseCitationIndex', () => {
    it('returns the raw marker number, 1-based or not', () => {
      expect(parseCitationIndex('[ID:1]')).toBe(1);
      expect(parseCitationIndex('[ID:5]')).toBe(5);
      expect(parseCitationIndex('5')).toBe(5);
      expect(parseCitationIndex('[7]')).toBe(7);
    });

    it('returns NaN when the text carries no marker', () => {
      expect(Number.isNaN(parseCitationIndex('no marker here'))).toBe(true);
      expect(Number.isNaN(parseCitationIndex(''))).toBe(true);
    });

    it('keeps marker 0 intact for the 0-based ask flow', () => {
      // pages/next-search indexes with this value directly, so it must not be
      // shifted here.
      expect(parseCitationIndex('[ID:0]')).toBe(0);
    });
  });

  describe('citedChunkIndex', () => {
    it('converts a 1-based marker into a 0-based pool index', () => {
      expect(citedChunkIndex('[ID:1]')).toBe(0);
      expect(citedChunkIndex('[ID:5]')).toBe(4);
      expect(citedChunkIndex('5')).toBe(4);
    });

    it('reports "no index" as -1 for every unusable marker', () => {
      // -1, never NaN: the renderers test `>= 0` and print the value otherwise,
      // which is how an unresolvable marker once rendered as "图 NaN".
      expect(citedChunkIndex('[ID:0]')).toBe(-1);
      for (const value of ['', '   ', '[', '[ID:]', '[]', 'abc', 'ID:5']) {
        expect(citedChunkIndex(value)).toBe(-1);
      }
      expect(citedChunkIndex(undefined as unknown as string)).toBe(-1);
      expect(citedChunkIndex(null as unknown as string)).toBe(-1);
    });

    it('never returns NaN, whatever the input', () => {
      const values = [
        '',
        '   ',
        '[',
        '[ID:]',
        '[]',
        '[ID:0]',
        '[ID:1]',
        '[ID:6]',
        'abc',
        'ID:5',
        undefined,
        null,
        0,
      ];

      for (const value of values) {
        for (const poolSize of [undefined, 0, 5]) {
          const index = citedChunkIndex(value as unknown as string, poolSize);
          expect(Number.isNaN(index)).toBe(false);
          expect(index).toBeGreaterThanOrEqual(-1);
        }
      }
    });

    it('rejects a marker outside the pool when the pool size is known', () => {
      expect(citedChunkIndex('[ID:5]', 5)).toBe(4);
      expect(citedChunkIndex('[ID:6]', 5)).toBe(-1);
    });

    it('rejects every marker while the pool is still empty', () => {
      // The backend sends the reference with the final event only, so the pool
      // is empty for the whole stream: no chip may be rendered before it lands.
      expect(citedChunkIndex('[ID:1]', 0)).toBe(-1);
      expect(citedChunkIndex('[ID:5]', 0)).toBe(-1);
    });

    it('keeps an in-range marker when no pool size is supplied', () => {
      expect(citedChunkIndex('[ID:1]')).toBe(0);
      expect(citedChunkIndex('[ID:1]', undefined)).toBe(0);
    });
  });
});
