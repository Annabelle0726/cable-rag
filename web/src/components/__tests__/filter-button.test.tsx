import ListFilterBar, { FilterButton } from '@/components/list-filter-bar';
import { Button } from '@/components/ui/button';
import { render, screen } from '@testing-library/react';
import fs from 'fs';
import path from 'path';

const classList = (element: HTMLElement) => element.className.split(/\s+/);

// The list toolbars are the one place where every page has to look identical, so
// the shared pieces are pinned here. The 国网 skin is a flat 32px rail: a 1px
// hairline, 2px corners and no elevation on either the funnel or the search field.
describe('list toolbar controls', () => {
  it('dresses the funnel as a flat 32px control', () => {
    render(<FilterButton />);

    const funnel = screen.getByRole('button');

    expect(classList(funnel)).toEqual(
      expect.arrayContaining([
        'ceramic-relief',
        'h-8',
        'rounded-[2px]',
        'w-8',
        'text-text-secondary',
      ]),
    );
    // No `size-*` shorthand: that is what dragged the box off the rail it shares
    // with the search field and the create button.
    expect(classList(funnel).some((name) => /^size-\d/.test(name))).toBe(false);
  });

  it('keeps the same rail when the funnel carries a count', () => {
    render(<FilterButton count={3} />);

    const funnel = screen.getByRole('button');

    expect(classList(funnel)).toEqual(
      expect.arrayContaining(['ceramic-relief', 'h-8', 'px-3', 'rounded-[2px]']),
    );
    expect(funnel.className).not.toMatch(/\bw-8\b/);
    expect(funnel).toHaveTextContent('3');
  });

  it('right-aligns the control row on the shared 8px rhythm', () => {
    render(
      <ListFilterBar
        title="智能体"
        filters={[{ field: 'owner', label: 'Owner', list: [] }]}
        value={{}}
        onChange={jest.fn()}
      >
        <Button className="ceramic-cta h-8 rounded-[2px] px-3">+</Button>
      </ListFilterBar>,
    );

    const toolbar = screen.getByRole('toolbar');

    expect(classList(toolbar)).toEqual(
      expect.arrayContaining([
        'items-center',
        'gap-2',
        'md:justify-end',
        'md:shrink-0',
      ]),
    );

    // The search field keeps the create action at arm's length: on the bare 8px
    // rhythm the two read as a single control.
    expect(screen.getByRole('searchbox').parentElement?.className).toMatch(
      /me-2/,
    );
  });

  it('draws the search field as a 1px-bordered 32px box and insets its text past the icon', () => {
    render(<ListFilterBar title="知识库" value={{}} onChange={jest.fn()} />);

    const field = screen.getByRole('searchbox');
    const wrapper = field.parentElement as HTMLElement;

    expect(classList(field)).toEqual(
      expect.arrayContaining(['ceramic-well', 'h-8', 'rounded-[2px]', 'px-3']),
    );
    // `Input` writes its inline padding-inline-start from the measured prefix
    // span, so the lead-in has to live on that span for the text to start after
    // the magnifier instead of under it.
    expect(wrapper.className).toMatch(/\[&>span\]:ps-2\.5/);
    expect(wrapper.className).toMatch(/\[&>span>svg\]:ms-0/);
  });
});

// The mechanism behind the fix, not just its call sites: a primitive paints its
// own surface (`bg-text-primary`, `bg-bg-input`), and a class in the components
// layer is emitted before those utilities, so it loses on equal specificity. The
// shared surfaces therefore have to live in the utilities layer.
describe('shared surfaces', () => {
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
