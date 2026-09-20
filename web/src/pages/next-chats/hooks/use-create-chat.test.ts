import { act, renderHook } from '@testing-library/react';
import { useCreateChatDialog } from './use-create-chat';

// The dictionary and the warning are the two inputs this hook decides on, so both
// are stubbed; the dialog's own visibility comes from the real `useSetModalState`.
const mockDictionary = {
  embd_id: 'model@default@openai',
  llm_id: 'model@default@openai',
};

jest.mock('@/hooks/use-llm-request', () => ({
  useFetchDefaultModelDictionary: () => mockDictionary,
}));

jest.mock('@/hooks/use-chat-request', () => ({
  useCreateChat: () => ({ createChat: jest.fn(), loading: false }),
}));

jest.mock('@/hooks/use-warn-empty-model', () => ({
  warnAboutEmptyModel: jest.fn(),
}));

jest.mock('@/hooks/logic-hooks/navigate-hooks', () => ({
  useNavigatePage: () => ({ navigateToModelSetting: jest.fn() }),
}));

const { warnAboutEmptyModel } = jest.requireMock(
  '@/hooks/use-warn-empty-model',
);

const withDictionary = (embd_id: string, llm_id: string) => {
  mockDictionary.embd_id = embd_id;
  mockDictionary.llm_id = llm_id;
};

beforeEach(() => {
  jest.clearAllMocks();
  withDictionary('model@default@openai', 'model@default@openai');
});

/**
 * The create dialog is only worth opening when the tenant can actually build an
 * assistant: with no default model the completion path refuses, so the dialog's Save
 * would produce nothing.
 */
describe('create-chat dialog', () => {
  it('opens when a default embedding model and LLM are set', () => {
    const { result } = renderHook(() => useCreateChatDialog());

    act(() => result.current.showCreateChatModal());

    expect(result.current.createChatVisible).toBe(true);
    expect(warnAboutEmptyModel).not.toHaveBeenCalled();
  });

  it('warns instead of opening when the LLM default is missing', () => {
    withDictionary('model@default@openai', '');
    const { result } = renderHook(() => useCreateChatDialog());

    act(() => result.current.showCreateChatModal());

    expect(warnAboutEmptyModel).toHaveBeenCalledTimes(1);
    expect(result.current.createChatVisible).toBe(false);
  });

  it('warns instead of opening when the embedding default is missing', () => {
    withDictionary('', 'model@default@openai');
    const { result } = renderHook(() => useCreateChatDialog());

    act(() => result.current.showCreateChatModal());

    expect(warnAboutEmptyModel).toHaveBeenCalledTimes(1);
    expect(result.current.createChatVisible).toBe(false);
  });
});
