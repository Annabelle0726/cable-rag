import { fireEvent, render, screen } from '@testing-library/react';
import { useHandleMessageInputChange } from '../logic-hooks';

// logic-hooks reaches the router, which builds a browser router at module scope
// and needs a global Request that jsdom does not provide; the request hooks it
// also pulls in are irrelevant to this handler.
jest.mock('../route-hook', () => ({
  useSetPaginationParams: () => jest.fn(),
}));
jest.mock('../use-user-setting-request', () => ({
  useSaveSetting: () => jest.fn(),
}));
jest.mock('eventsource-parser/stream', () => ({}));

/** The chat input, wired the same way the page wires it. */
function ChatInput() {
  const { handleInputChange, value } = useHandleMessageInputChange();

  return (
    <>
      <textarea
        aria-label="question"
        value={value}
        onChange={handleInputChange}
      />
      <output data-testid="typed">{value}</output>
    </>
  );
}

const typeQuestion = (question: string) => {
  render(<ChatInput />);
  fireEvent.change(screen.getByLabelText('question'), {
    target: { value: question },
  });

  return screen.getByTestId('typed').textContent;
};

describe('useHandleMessageInputChange', () => {
  it('keeps a LaTeX question verbatim', () => {
    const question = '标称截面为 $1.5 \\text{mm}^2$ 的电缆，$a \\times b$ 如何取值？';

    const typed = typeQuestion(question);

    expect(typed).toBe(question);
    // A tab or a line break here would break the math rendering downstream.
    expect(typed).not.toContain('\t');
    expect(typed).not.toContain('\n');
  });

  it('keeps escaped letters exactly as typed', () => {
    expect(typeQuestion('C:\\new\\table\\text')).toBe('C:\\new\\table\\text');
  });
});
