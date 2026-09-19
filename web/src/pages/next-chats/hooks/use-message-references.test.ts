import { resolveAnswerPools } from './use-message-references';
// Type-only: this file must not hand jest a value binding that is only used in an
// annotation.
import type { IReference } from '@/interfaces/database/chat';

/** Only the pool itself matters here, so the fixture carries nothing else. */
const buildPool = (label: string) =>
  ({ chunks: [{ id: label }], doc_aggs: [], total: 1 }) as unknown as IReference;

const EMPTY_POOL = { chunks: [], doc_aggs: [], total: 0 } as unknown as IReference;

/**
 * The tool loop answers straight from the conversation history when it decides no
 * retrieval is needed, and that answer still quotes the previous answer's
 * `[ID:n]` markers. Those markers index the previous pool, so an answer whose own
 * entry is empty has to inherit it — otherwise every marker in the answer is
 * unresolvable and its citations degrade to bare digits with nothing to open.
 */
describe('resolveAnswerPools', () => {
  it('passes through the pools that are present', () => {
    const first = buildPool('first');
    const second = buildPool('second');

    expect(resolveAnswerPools([first, second])).toEqual([first, second]);
  });

  it('gives an empty entry the pool of the answer before it', () => {
    const first = buildPool('first');
    const third = buildPool('third');

    expect(resolveAnswerPools([first, EMPTY_POOL, third])).toEqual([
      first,
      first,
      third,
    ]);
  });

  it('leaves a leading empty entry unresolved', () => {
    const second = buildPool('second');

    // Nothing precedes it, so there is no pool those markers could point at.
    expect(resolveAnswerPools([EMPTY_POOL, second])[0]).toBeUndefined();
    expect(resolveAnswerPools([EMPTY_POOL, second])[1]).toBe(second);
  });

  it('handles a missing reference list', () => {
    expect(resolveAnswerPools(undefined)).toEqual([]);
  });
});
