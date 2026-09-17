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

    it('rejects marker 0, which 1-based citations never emit', () => {
      expect(Number.isNaN(citedChunkIndex('[ID:0]'))).toBe(true);
    });

    it('rejects a marker outside the pool when the pool size is known', () => {
      expect(citedChunkIndex('[ID:5]', 5)).toBe(4);
      expect(Number.isNaN(citedChunkIndex('[ID:6]', 5))).toBe(true);
    });

    it('returns NaN instead of throwing on malformed input', () => {
      for (const value of ['', '   ', '[', '[ID:]', '[]', 'abc', 'ID:5']) {
        expect(Number.isNaN(citedChunkIndex(value))).toBe(true);
      }
      expect(Number.isNaN(citedChunkIndex(undefined as unknown as string))).toBe(
        true,
      );
    });
  });
});
