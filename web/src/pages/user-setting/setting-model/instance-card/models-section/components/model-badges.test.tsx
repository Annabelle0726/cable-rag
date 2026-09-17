import { render, screen } from '@testing-library/react';
import { ModelTypeBadges } from './model-type-badges';
import { TagFilterButton } from './tag-filter-button';

// The badge component reaches the model hooks, whose module chain builds the app
// router at import time (which needs web globals jsdom lacks).
jest.mock('@/hooks/use-llm-request', () => ({
  useFetchInstanceModels: () => ({ data: [], loading: false }),
  useFetchAllAddedModels: () => ({ data: [], isFetched: true }),
  useFetchAddedProviders: () => ({ data: [] }),
  useFetchAvailableProviders: () => ({ data: [] }),
}));

// The chips on this page were flat grey blocks, and the active tag filter painted
// the theme's ink (black in light mode) — both of which read as a different
// material from the toolbars around them.
describe('model settings chips', () => {
  it('renders a model type as a mini ceramic badge', () => {
    const { container } = render(
      <ModelTypeBadges types={['chat']} showEdit={false} />,
    );

    const badge = container.querySelector('.ceramic-badge');

    expect(badge).not.toBeNull();
    expect(badge?.className).not.toMatch(/bg-bg-card|bg-text-primary/);
  });

  it('marks the active tag filter with the brand fill and idles the rest', () => {
    const { rerender } = render(
      <TagFilterButton label="All" count={3} active />,
    );

    expect(screen.getByRole('button').className).toMatch(/ceramic-cta/);

    rerender(<TagFilterButton label="All" count={3} active={false} />);

    expect(screen.getByRole('button').className).toMatch(/ceramic-badge/);
    expect(screen.getByRole('button').className).not.toMatch(
      /bg-text-primary|bg-bg-card/,
    );
  });
});
