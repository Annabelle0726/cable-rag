import message from '@/components/ui/message';
import notification from '@/utils/notification';
import i18n from '@/locales/config';
import request from '../next-request';

jest.mock('@/components/ui/message', () => ({
  __esModule: true,
  default: {
    error: jest.fn(),
    success: jest.fn(),
    warning: jest.fn(),
    info: jest.fn(),
  },
}));

jest.mock('@/utils/notification', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

/** The provider body that used to reach the screen verbatim. */
const RAW_BODY =
  '429 RESOURCE_EXHAUSTED. {\'error\': {\'code\': 429, \'message\': "You exceeded your current quota", \'details\': [{\'quotaId\': \'EmbedContentRequestsPerDayPerProjectPerModel-FreeTier\'}]}}';

const answerWith = (body: unknown) => {
  request.defaults.adapter = async (config: any) => ({
    data: body,
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  });
};

const everyNotificationText = () =>
  JSON.stringify([
    ...(message.error as jest.Mock).mock.calls,
    ...(notification.error as jest.Mock).mock.calls,
  ]);

beforeEach(() => {
  jest.clearAllMocks();
});

describe('a provider refusal reaching the request layer', () => {
  it('shows the sentence and never the upstream body', async () => {
    answerWith({
      code: 429,
      message: 'AI 向量化服务额度已耗尽，请更换 API Key 或等待额度重置后重试。',
      error_type: 'EMBEDDING_QUOTA_EXHAUSTED',
      raw_message: RAW_BODY,
    });

    await request.post('/v1/datasets/search', {});

    expect(message.error).toHaveBeenCalledWith(
      i18n.t('message.embeddingQuotaExhausted'),
    );
    // The whole point: the upstream JSON must not reach a toast.
    expect(everyNotificationText()).not.toContain('RESOURCE_EXHAUSTED');
    expect(everyNotificationText()).not.toContain('quotaId');
    // Nor the hint-and-code notification it used to be rendered by.
    expect(notification.error).not.toHaveBeenCalled();
  });

  it('answers a per-minute limit with its own wording', async () => {
    answerWith({
      code: 429,
      message: 'ignored in favour of the translated key',
      error_type: 'EMBEDDING_RATE_LIMITED',
      raw_message: RAW_BODY,
    });

    await request.post('/v1/chat/mindmap', {});

    expect(message.error).toHaveBeenCalledWith(
      i18n.t('message.embeddingRateLimited'),
    );
    expect(notification.error).not.toHaveBeenCalled();
  });

  it('keeps the previous handling for an error it does not recognise', async () => {
    answerWith({ code: 102, message: 'Data missing!' });

    await request.post('/v1/searches', {});

    expect(notification.error).toHaveBeenCalled();
    expect(message.error).not.toHaveBeenCalled();
  });

  it('caps an unmapped message so a stack cannot fill a notification', async () => {
    const long = 'x'.repeat(5000);
    answerWith({ code: 102, message: long });

    await request.post('/v1/searches', {});

    const description = (notification.error as jest.Mock).mock.calls[0][0]
      .description;
    expect(description.length).toBeLessThan(400);
    expect(description.endsWith('…')).toBe(true);
  });

  it('still respects a caller that silences the global notification', async () => {
    answerWith({
      code: 429,
      error_type: 'EMBEDDING_QUOTA_EXHAUSTED',
      raw_message: RAW_BODY,
    });

    await request.post('/v1/datasets/search', {}, {
      skipGlobalErrorNotification: true,
    } as never);

    expect(message.error).not.toHaveBeenCalled();
    expect(notification.error).not.toHaveBeenCalled();
  });
});
