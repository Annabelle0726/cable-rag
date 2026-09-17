import ListFilterBar, { FilterButton } from '@/components/list-filter-bar';
import { Button } from '@/components/ui/button';
import { render, screen } from '@testing-library/react';
import fs from 'fs';
import path from 'path';

const classList = (element: HTMLElement) => element.className.split(/\s+/);

// The list toolbars are the one place where every page has to look identical, so
// the shared pieces are pinned here. The ink-filled default button and the glass
// funnel used to be pushed through the primitive's own surface utilities, which
// are emitted after a components-layer class and therefore won.
describe('list toolbar controls', () => {
  it('dresses the funnel as a 40px glass control', () => {
    render(<FilterButton />);

    const funnel = screen.getByRole('button');

    expect(classList(funnel)).toEqual(
      expect.arrayContaining([
        'ceramic-relief',
        'h-10',
        'rounded-full',
        'w-10',
        'text-text-secondary',
      ]),
    );
    // No `size-*` shorthand: that is what dragged the box off the 40px rail it
    // shares with the search field and the create button.
    expect(classList(funnel).some((name) => /^size-\d/.test(name))).toBe(false);
  });

  it('keeps the same rail when the funnel carries a count', () => {
    render(<FilterButton count={3} />);

    const funnel = screen.getByRole('button');

    expect(classList(funnel)).toEqual(
      expect.arrayContaining(['ceramic-relief', 'h-10', 'px-4', 'rounded-full']),
    );
    expect(funnel.className).not.toMatch(/\bw-10\b/);
    expect(funnel).toHaveTextContent('3');
  });

  it('right-aligns the control row on the shared 12px rhythm', () => {
    render(
      <ListFilterBar
        title="智能体"
        filters={[{ field: 'owner', label: 'Owner', list: [] }]}
        value={{}}
        onChange={jest.fn()}
      >
        <Button className="ceramic-cta h-10 rounded-full px-5">+</Button>
      </ListFilterBar>,
    );

    const toolbar = screen.getByRole('toolbar');

    expect(classList(toolbar)).toEqual(
      expect.arrayContaining([
        'items-center',
        'gap-3',
        'md:justify-end',
        'md:shrink-0',
      ]),
    );
  });
});

// The mechanism behind the fix, not just its call sites: a primitive paints its
// own surface (`bg-text-primary`, `bg-bg-input`), and a class in the components
// layer is emitted before those utilities, so it loses on equal specificity. Both
// ceramic surfaces therefore have to live in the utilities layer.
describe('ceramic surfaces', () => {
  it('are declared in the utilities layer so a primitive cannot outrank them', () => {
    const css = fs.readFileSync(
      path.resolve(__dirname, '../../../tailwind.css'),
      'utf8',
    );
    const utilitiesStart = css.lastIndexOf('@layer utilities {');

    expect(utilitiesStart).toBeGreaterThan(-1);
    ['.ceramic-cta {', '.ceramic-relief {'].forEach((selector) => {
      expect(css.indexOf(selector)).toBeGreaterThan(utilitiesStart);
    });
  });
});
