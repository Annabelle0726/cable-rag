import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import MindMapViewer from '../mind-map-viewer';

// The mind map is drawn into a canvas, so nothing inside it is reachable from
// the DOM: what a test can pin is the contract the view hands G6 — which
// gestures are live, what the map looks like when it opens, and what the
// toolbar does to the viewport.

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock('@antv/g6', () => {
  const graph = {
    destroyed: false,
    on: jest.fn(),
    off: jest.fn(),
    setOptions: jest.fn(),
    setData: jest.fn(),
    render: jest.fn(() => Promise.resolve()),
    resize: jest.fn(),
    getSize: jest.fn(() => [0, 0]),
    getZoom: jest.fn(() => 1),
    zoomBy: jest.fn(() => Promise.resolve()),
    zoomTo: jest.fn(() => Promise.resolve()),
    translateTo: jest.fn(() => Promise.resolve()),
    fitView: jest.fn(() => Promise.resolve()),
    getNodeData: jest.fn(() => [{ id: 'root', depth: 0 }]),
    getElementRenderBounds: jest.fn(() => ({ min: [10, 10], max: [110, 40] })),
    destroy: jest.fn(),
  };

  // A faithful-enough stand-in for G6's tree flattening: nodes carry a depth
  // and their child ids, which is what the drawing code reads.
  const flatten = (node: any, depth = 0, nodes: any[] = []): any[] => {
    nodes.push({
      ...node,
      depth,
      children: (node.children ?? []).map((child: any) => child.id),
    });
    (node.children ?? []).forEach((child: any) => flatten(child, depth + 1, nodes));
    return nodes;
  };

  return {
    __graph: graph,
    Graph: jest.fn(() => graph),
    GraphEvent: { AFTER_TRANSFORM: 'aftertransform' },
    treeToGraphData: (tree: any) => ({ nodes: flatten(tree), edges: [] }),
  };
});

const mockGraph = (jest.requireMock('@antv/g6') as any).__graph;

const tree = {
  id: '线缆技术要求',
  children: [
    {
      id: '执行标准',
      children: [
        {
          id: '绝缘厚度',
          children: [{ id: '表2', children: [{ id: '深层节点' }] }],
        },
      ],
    },
  ],
};

const nodesGivenToGraph = () => mockGraph.setData.mock.calls.at(-1)[0].nodes;

beforeEach(() => {
  jest.clearAllMocks();
  mockGraph.getZoom.mockReturnValue(1);
  mockGraph.render.mockImplementation(() => Promise.resolve());
});

describe('mind map viewer', () => {
  it('opens with the first levels expanded and the rest collapsed', async () => {
    render(<MindMapViewer data={tree} />);

    await waitFor(() => expect(mockGraph.setData).toHaveBeenCalled());

    const byDepth = new Map<string, any>(
      nodesGivenToGraph()
        .filter((node: any) => node.children.length > 0)
        .map((node: any) => [node.id, node]),
    );

    expect(byDepth.get('线缆技术要求').style.collapsed).toBe(false);
    expect(byDepth.get('执行标准').style.collapsed).toBe(false);
    expect(byDepth.get('绝缘厚度').style.collapsed).toBe(false);
    expect(byDepth.get('表2').style.collapsed).toBe(true);
    // A leaf owns no subtree, so it must not advertise a disclosure.
    expect(
      nodesGivenToGraph().find((node: any) => node.id === '深层节点').style
        .collapsed,
    ).toBe(false);
  });

  it('leaves the map at real size instead of shrinking it to fit', async () => {
    render(<MindMapViewer data={tree} />);

    await waitFor(() => expect(mockGraph.translateTo).toHaveBeenCalled());

    expect(mockGraph.zoomTo).toHaveBeenCalledWith(1);
    // The root lands at the canvas padding, translated by its own bounds.
    expect(mockGraph.translateTo).toHaveBeenCalledWith([24 - 10, 24 - 10]);
    const options = mockGraph.setOptions.mock.calls.at(-1)[0];
    expect(options.zoomRange).toEqual([0.2, 3]);
  });

  it('arms the wheel, the pointer drag and a click on a node', async () => {
    render(<MindMapViewer data={tree} />);

    await waitFor(() => expect(mockGraph.setOptions).toHaveBeenCalled());

    const behaviors = mockGraph.setOptions.mock.calls.at(-1)[0].behaviors;
    const byType = Object.fromEntries(
      behaviors.map((behavior: any) => [behavior.type, behavior]),
    );

    // G6's own drag-canvas refuses a drag that starts on a node, which is every
    // drag on a map that fills its panel.
    expect(byType['drag-canvas'].enable).toBe(true);
    expect(byType['zoom-canvas']).toBeDefined();
    expect(byType['collapse-expand'].trigger).toBe('click');
  });

  it('reports the scale a transform left behind', async () => {
    render(<MindMapViewer data={tree} />);
    await waitFor(() => expect(mockGraph.on).toHaveBeenCalled());

    const [event, handler] = mockGraph.on.mock.calls.at(-1);
    expect(event).toBe('aftertransform');

    mockGraph.getZoom.mockReturnValue(1.5);
    act(() => {
      handler();
    });

    expect(screen.getByTestId('mindmap-zoom-reset')).toHaveTextContent('150%');
  });

  it('drives the viewport from the toolbar', async () => {
    render(<MindMapViewer data={tree} />);
    await waitFor(() => expect(mockGraph.translateTo).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId('mindmap-zoom-in'));
    expect(mockGraph.zoomBy).toHaveBeenLastCalledWith(1.25, expect.anything());

    fireEvent.click(screen.getByTestId('mindmap-zoom-out'));
    expect(mockGraph.zoomBy).toHaveBeenLastCalledWith(0.8, expect.anything());

    fireEvent.click(screen.getByTestId('mindmap-fit-view'));
    expect(mockGraph.fitView).toHaveBeenCalledWith(
      { when: 'always' },
      expect.anything(),
    );

    mockGraph.zoomTo.mockClear();
    fireEvent.click(screen.getByTestId('mindmap-zoom-reset'));
    await waitFor(() => expect(mockGraph.zoomTo).toHaveBeenCalledWith(1));
  });
});
