/**
 * Regression tests for the streamed reference pool.
 *
 * The backend sends the reference (the chunk pool every citation resolves
 * against) with the final event, and empty `reference: {}` on the deltas. Chunks
 * are coalesced into one store write per flush window by merging fields, so an
 * empty reference arriving on a later chunk used to overwrite the pool an
 * earlier one had delivered — the answer then rendered citations against
 * nothing.
 */

jest.mock('../store', () => {
  const store = {
    beginStream: jest.fn(() => true),
    applyAnswer: jest.fn(),
    endStream: jest.fn(),
  };

  return {
    __store: store,
    useChatStreamStore: { getState: () => store },
  };
});

jest.mock('@/services/chat-completion-stream', () => {
  const holder: { chunks: unknown[] } = { chunks: [] };

  return {
    __holder: holder,
    requestChatCompletionStream: jest.fn(async () => ({
      status: 200,
      clone: () => ({
        json: async () => {
          throw new Error('the stream body is not JSON');
        },
      }),
    })),
    parseCompletionEventStream: () =>
      (async function* () {
        for (const chunk of holder.chunks) {
          yield chunk;
        }
      })(),
    readJsonSafely: jest.fn(async () => undefined),
  };
});

import { runChatCompletionStream } from '../run-stream';

const { __store: mockStore } = jest.requireMock('../store');
const { __holder: chunkHolder } = jest.requireMock(
  '@/services/chat-completion-stream',
);

const pool = { chunks: [{ id: 'chunk-1', content_with_weight: '护套 PUR' }] };

const appliedChunk = () => {
  const calls = mockStore.applyAnswer.mock.calls;
  return calls[calls.length - 1][1];
};

describe('runChatCompletionStream reference pool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    chunkHolder.chunks = [];
    // A fixed clock keeps every chunk after the first inside one flush window,
    // which is where the merge happens.
    jest.spyOn(Date, 'now').mockReturnValue(1_000);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('keeps the pool when a later chunk carries an empty reference', async () => {
    chunkHolder.chunks = [
      { answer: '见表 ', reference: {} },
      { answer: '1。', reference: pool },
      { answer: '', reference: {}, final: true },
    ];

    await runChatCompletionStream({
      conversationId: 'conv-1',
      messages: [],
    });

    expect(appliedChunk().reference).toEqual(pool);
  });

  it('lets a later non-empty reference replace the buffered one', async () => {
    const finalPool = { chunks: [{ id: 'chunk-2', content_with_weight: '外径 6.60' }] };
    chunkHolder.chunks = [
      { answer: '见表 ', reference: pool },
      { answer: '1。', reference: finalPool, final: true },
    ];

    await runChatCompletionStream({
      conversationId: 'conv-1',
      messages: [],
    });

    expect(appliedChunk().reference).toEqual(finalPool);
  });

  it('writes the whole accumulated answer on the final flush', async () => {
    chunkHolder.chunks = [
      { answer: '护套为 ', reference: {} },
      { answer: 'PUR 紫色。', reference: {} },
      { answer: '', reference: pool, final: true },
    ];

    await runChatCompletionStream({
      conversationId: 'conv-1',
      messages: [],
    });

    expect(appliedChunk().answer).toBe('护套为 PUR 紫色。');
    expect(appliedChunk().reference).toEqual(pool);
    expect(mockStore.endStream).toHaveBeenCalledWith('conv-1');
  });
});
