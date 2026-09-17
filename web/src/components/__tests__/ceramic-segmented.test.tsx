import { fireEvent, render, screen } from '@testing-library/react';
import { CeramicSegmented } from '../ceramic-segmented';

// jsdom cannot evaluate anchor positioning either way, so the flag is driven from
// the test: both rendering paths have to look right.
const mockCssSupport = { supported: false };

jest.mock('@/utils/css-support', () => ({
  get supportsCssAnchor() {
    return mockCssSupport.supported;
  },
}));

const options = [
  { value: '/chats', label: '聊天' },
  { value: '/searches', label: '搜索' },
  { value: '/agents', label: '智能体' },
  { value: '/memories', label: '记忆' },
];

const renderControl = (onChange = jest.fn()) => {
  render(
    <CeramicSegmented options={options} value="/chats" onChange={onChange} />,
  );

  return onChange;
};

describe('ceramic segmented control', () => {
  beforeEach(() => {
    mockCssSupport.supported = false;
  });

  it('renders every tab and marks the selected one', () => {
    renderControl();

    options.forEach((option) => {
      expect(screen.getByTestId(`ceramic-segment-${option.value}`)).toHaveTextContent(
        String(option.label),
      );
    });

    expect(screen.getByTestId('ceramic-segment-/chats')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByTestId('ceramic-segment-/searches')).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('wears the ceramic shell on the capsule and the raised pill on the tab', () => {
    renderControl();

    // The recessed groove is the container; with no anchor support the selected
    // tab itself is the raised piece.
    expect(screen.getByRole('group')).toHaveClass('ceramic-segmented');
    expect(screen.getByTestId('ceramic-segment-/chats')).toHaveClass(
      'ceramic-segment-pill',
    );
    expect(screen.getByTestId('ceramic-segment-/searches')).toHaveClass(
      'ceramic-segment-idle',
    );
    expect(screen.queryByTestId('ceramic-segment-pill')).not.toBeInTheDocument();
  });

  it('slides a separate ceramic pill over the selected tab when anchors are supported', () => {
    mockCssSupport.supported = true;

    renderControl();

    expect(screen.getByTestId('ceramic-segment-pill')).toHaveClass(
      'ceramic-segment-pill',
    );
    // The tab keeps its label styling only; the pill carries the material.
    expect(screen.getByTestId('ceramic-segment-/chats')).not.toHaveClass(
      'ceramic-segment-pill',
    );
  });

  it('reports the tab that was pressed', () => {
    const onChange = renderControl();

    fireEvent.click(screen.getByTestId('ceramic-segment-/agents'));

    expect(onChange).toHaveBeenCalledWith('/agents');
  });
});
