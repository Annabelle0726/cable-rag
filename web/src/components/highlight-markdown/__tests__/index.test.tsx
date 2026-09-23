import { render } from '@testing-library/react';
import React from 'react';

import HighLightMarkdown from '..';

// These specs deliberately do NOT mock react-markdown, rehype-raw or
// rehype-sanitize. An earlier revision replaced react-markdown with a
// `dangerouslySetInnerHTML` div and stubbed rehype-raw, which removed the whole
// pipeline under test: the mock received the post-preprocessLaTeX string and
// injected it verbatim, so `<script>` reached the DOM regardless of what the
// component did and the assertions could never pass. Driving the real pipeline
// is the only way these can mean anything.
//
// What the component wires up (highlight-markdown/index.tsx):
//   preprocessLaTeX(...)            decodes &lt;/&gt;/&amp; back into markup
//   rehypeRaw                       parses that markup into real nodes
//   RehypeSanitizeAssistantMarkdown applies the allow-list
//   rehypeKatex                     renders math last
// The ordering matters: sanitizing before preprocessLaTeX would inspect inert
// entity text and let the payload become live afterwards.

jest.mock('react-syntax-highlighter', () => ({
  Prism: ({ children }: any) => {
    const react = jest.requireActual('react');
    return react.createElement('pre', null, children);
  },
}));

jest.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  oneDark: {},
  oneLight: {},
}));

jest.mock('../../theme-provider', () => ({
  useIsDarkTheme: () => false,
}));

/** Assert nothing in the tree can execute script. */
const expectNoScriptSink = (container: HTMLElement) => {
  expect(container.querySelector('script')).toBeNull();
  expect(container.querySelector('iframe')).toBeNull();
  expect(container.querySelector('object')).toBeNull();
  expect(container.querySelector('embed')).toBeNull();
  container.querySelectorAll('*').forEach((el) => {
    Array.from(el.attributes).forEach((attr) => {
      expect(attr.name.toLowerCase().startsWith('on')).toBe(false);
    });
  });
};

describe('HighLightMarkdown sanitisation', () => {
  it('keeps allowed markup and drops an inline script', () => {
    const { container } = render(
      React.createElement(
        HighLightMarkdown,
        null,
        'hello <b>safe</b><script>alert(1)</script>',
      ),
    );

    // Proves rehypeRaw ran: the tag became a real element, not text.
    expect(container.querySelector('b')?.textContent).toBe('safe');
    expectNoScriptSink(container);
  });

  it('blocks an entity-encoded payload that preprocessLaTeX decodes into markup', () => {
    // The bypass this guards: `&lt;script&gt;` is inert while a pre-parse
    // string check inspects it, and preprocessLaTeX turns it back into a live
    // tag afterwards. Sanitising the parsed tree closes that window.
    const { container } = render(
      React.createElement(
        HighLightMarkdown,
        null,
        '&lt;script&gt;alert(1)&lt;/script&gt;&lt;b&gt;safe&lt;/b&gt;',
      ),
    );

    // The entity-encoded <b> did become a real element...
    expect(container.querySelector('b')?.textContent).toBe('safe');
    // ...while the entity-encoded <script> did not survive.
    expectNoScriptSink(container);
  });

  it('never lets an inline event handler survive', () => {
    const { container } = render(
      React.createElement(
        HighLightMarkdown,
        null,
        'hello <img src="https://example.test/x.png" onerror="alert(1)" />',
      ),
    );

    // The handler may be stripped or the whole tag dropped. Both are safe; what
    // matters is that no handler reaches the DOM.
    const img = container.querySelector('img');
    if (img) {
      expect(img.getAttribute('onerror')).toBeNull();
    }
    expectNoScriptSink(container);
  });

  it('drops a tag whose src protocol is not allowed', () => {
    const { container } = render(
      React.createElement(HighLightMarkdown, null, '<img src="x" />'),
    );

    // A bare, protocol-less src is not in the allow-list, so the tag goes.
    expect(container.querySelector('img')).toBeNull();
  });

  it('leaves prose alone, including the characters KaTeX and code spans need', () => {
    const { container } = render(
      React.createElement(
        HighLightMarkdown,
        null,
        'a < b and `Array<number>`',
      ),
    );

    // A string-level escape pass would corrupt `a < b` (which KaTeX needs) and
    // the generic inside the code span. Node-level sanitising permits both.
    expect(container.textContent).toContain('a < b');
    expect(container.textContent).toContain('Array<number>');
  });
});
