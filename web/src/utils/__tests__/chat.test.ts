import {
  bumpConversation,
  countAgenticLogLines,
  generateTemporaryConversationId,
  isAgenticLogContinuation,
  isAgenticLogLine,
  isAgenticPreambleLine,
  isPersistedConversationId,
  isTemporaryConversationId,
  orderConversations,
  pinConversation,
  preprocessLaTeX,
  promoteCaretExponentsToLaTeX,
  replaceAgenticLogsToSection,
  replaceThinkToSection,
  trimExtractionResidue,
} from '../chat';
// Type-only: a value import used in an annotation fails the Babel transform that
// this suite's module graph is built with.
import type { IConversation } from '@/interfaces/database/chat';

describe('preprocessLaTeX', () => {
  it('converts block \\[ \\] to $$ $$', () => {
    expect(preprocessLaTeX('\\[ x + y \\]')).toBe('$$x + y$$');
  });

  it('converts inline \\( \\) to $ $', () => {
    expect(preprocessLaTeX('\\( a \\)')).toBe('$a$');
  });

  it('does not cut block math at \\right] (Closes #13134)', () => {
    const content =
      '\\[ C_{seq}(y|x) = \\frac{1}{|y|} \\sum_{t=1}^{|y|} \\right] \\]';
    const result = preprocessLaTeX(content);
    expect(result).toContain('\\right]');
    expect(result).toContain('\\frac{1}{|y|}');
    expect(result).toBe(
      '$$ C_{seq}(y|x) = \\frac{1}{|y|} \\sum_{t=1}^{|y|} \\right] $$',
    );
  });

  it('does not cut inline math at \\big) or nested parens', () => {
    const content = '\\( f(x) + \\big) \\)';
    const result = preprocessLaTeX(content);
    expect(result).toContain('\\big)');
    expect(result).toBe('$ f(x) + \\big) $');
  });

  it('handles multiple block equations', () => {
    const content = 'First \\[ a \\] then \\[ b \\right] c \\]';
    const result = preprocessLaTeX(content);
    expect(result).toBe('First $$a$$ then $$ b \\right] c $$');
  });

  it('handles double-escaped inline LaTeX', () => {
    expect(preprocessLaTeX('\\\\(\\\\Delta = b^2\\\\)')).toBe(
      '$\\Delta = b^2$',
    );
  });

  it('handles double-escaped block LaTeX', () => {
    expect(preprocessLaTeX('\\\\[E = mc^2\\\\]')).toBe('$$E = mc^2$$');
  });

  it('decodes HTML entities', () => {
    expect(preprocessLaTeX('a &lt; b &amp; c &gt; d')).toBe('a < b & c > d');
  });

  it('handles mixed double-escaped delimiters with HTML entities', () => {
    expect(preprocessLaTeX('\\\\(x &lt; y\\\\)')).toBe('$x < y$');
  });

  it('passes through already correct single-escaped delimiters unchanged', () => {
    expect(preprocessLaTeX('\\(x = 1\\)')).toBe('$x = 1$');
  });
});

describe('replaceThinkToSection', () => {
  it('drops an empty think section instead of rendering a bare strip', () => {
    expect(replaceThinkToSection('<think></think>Here is the answer.')).toBe(
      'Here is the answer.',
    );
  });

  it('drops a whitespace-only think section', () => {
    expect(replaceThinkToSection('<think>  \n </think>answer')).toBe('answer');
  });

  it('keeps a non-empty think section as a details block', () => {
    expect(replaceThinkToSection('<think>some reasoning</think>answer')).toBe(
      '<details class="think"><summary>Thinking...</summary>\n\nsome reasoning\n\n</details>\n\nanswer',
    );
  });

  it('uses the provided summary for non-empty sections', () => {
    expect(
      replaceThinkToSection('<think>reasoning</think>', 'Deep thought'),
    ).toBe(
      '<details class="think"><summary>Deep thought</summary>\n\nreasoning\n\n</details>',
    );
  });

  it('leaves text without think markers unchanged', () => {
    expect(replaceThinkToSection('plain answer')).toBe('plain answer');
  });

  it('gives an Agentic RAG think body the log panel instead of the reasoning label', () => {
    const result = replaceThinkToSection(
      '<think>[Agentic RAG] Starting research...\n[Keywords] cable</think>Answer',
      'Thought',
      'Log · {{num}}',
    );

    expect(result).toContain('<details class="agentic-log">');
    expect(result).toContain('<summary>Log · 2</summary>');
    expect(result).not.toContain('class="think"');
    expect(result.endsWith('Answer')).toBe(true);
  });

  it('keeps a reasoning think body on the generic summary when a log summary is passed', () => {
    const result = replaceThinkToSection(
      '<think>Step one.\nStep two.</think>Answer',
      'Thought',
      'Log · {{num}}',
    );

    expect(result).toBe(
      '<details class="think"><summary>Thought</summary>\n\nStep one.\nStep two.\n\n</details>\n\nAnswer',
    );
  });

  it('handles the Python wire shape where each log line is <br>-prefixed', () => {
    const result = replaceThinkToSection(
      '<think><br>[Hybrid search] Searching the knowledge base for "x"\n<br>[Keywords] cable\n</think>Answer',
      'Thought',
      'Log · {{num}}',
    );

    expect(result).toContain('<details class="agentic-log">');
    expect(result).toContain('<summary>Log · 2</summary>');
    expect(result).toContain('`[Hybrid search]` Searching the knowledge base for "x"');
    expect(result).toContain('`[Keywords]` cable');
    expect(result.endsWith('Answer')).toBe(true);
  });

  it('handles the Go wire shape where each log line ends with <br> and no newline', () => {
    const result = replaceThinkToSection(
      '<think>[Agentic RAG] Starting research — mode=hybrid<br>[Keywords] entity x1: copper<br></think>Answer',
      'Thought',
      'Log · {{num}}',
    );

    expect(result).toContain('<summary>Log · 2</summary>');
    expect(result).toContain('`[Agentic RAG]` Starting research — mode=hybrid');
    expect(result).toContain('`[Keywords]` entity x1: copper');
    expect(result).not.toContain('<br>');
    expect(result.endsWith('Answer')).toBe(true);
  });

  it('collapses a still-open think block so streaming never leaks logs', () => {
    const result = replaceThinkToSection(
      '<think>[Direct search] Looking up the knowledge base for: "x"',
      'Thought',
      'Log · {{num}}',
    );

    expect(result).toContain('<details class="agentic-log">');
    expect(result).toContain('<summary>Log · 1</summary>');
  });

  it('renders the panel body as markdown by leaving blank lines around it', () => {
    const result = replaceThinkToSection(
      '<think>[Keywords] **copper** alloy</think>Answer',
      'Thought',
      'Log · {{num}}',
    );

    // Markdown nested in a raw HTML block is only parsed once the block is
    // interrupted, hence the blank line after the summary and before </details>.
    expect(result).toContain('</summary>\n\n');
    expect(result).toContain('\n\n</details>');
    // The emphasis is left intact for react-markdown to parse.
    expect(result).toContain('**copper** alloy');
  });

  it('detaches the panel from the answer so the answer markdown is parsed', () => {
    // The backend joins the answer straight onto the closing tag, and CommonMark
    // keeps an HTML block open until a blank line: glued together, react-markdown
    // reads `**0.0991 Ω/km**` as raw HTML and prints the asterisks.
    const result = replaceThinkToSection(
      '<think>[Agentic RAG] Starting research...\n[Keywords] 185 mm²</think>上限值是 **0.0991 Ω/km** [ID:1]。',
      'Thought',
      'Log · {{num}}',
    );

    expect(result).toContain('</details>\n\n上限值是 **0.0991 Ω/km** [ID:1]。');
  });

  it('builds only one panel out of a think body that already became one', () => {
    const result = replaceAgenticLogsToSection(
      replaceThinkToSection(
        '<think>[Agentic RAG] Starting research...\n[Keywords] copper</think>上限值是 **0.0991 Ω/km**。',
        'Thought',
        'Log · {{num}}',
      ),
      'Log · {{num}}',
    );

    // The panel is finished output: re-scanning it used to strip its body into a
    // second panel and leave an empty first one behind.
    expect(result.match(/<details class="agentic-log">/g)).toHaveLength(1);
    expect(result.match(/<\/details>/g)).toHaveLength(1);
    expect(result).toContain('`[Keywords]` copper');
    expect(result.trimEnd().endsWith('上限值是 **0.0991 Ω/km**。')).toBe(true);
  });
});

describe('agentic RAG log extraction', () => {
  it('recognises every forwarded stage prefix', () => {
    expect(isAgenticLogLine('[Agentic RAG] Starting research...')).toBe(true);
    expect(isAgenticLogLine('[Formalize] query rewritten')).toBe(true);
    expect(isAgenticLogLine('[Keywords] "cable tray"')).toBe(true);
    expect(isAgenticLogLine('[Direct search] question')).toBe(true);
    expect(isAgenticLogLine('[Hybrid search] question')).toBe(true);
    expect(isAgenticLogLine('- [Keywords] list item form')).toBe(true);
    expect(isAgenticLogLine('Regular answer text')).toBe(false);
  });

  it('counts only the log lines', () => {
    expect(
      countAgenticLogLines('[Keywords] a\nAnswer text\n[Hybrid search] b'),
    ).toBe(2);
  });

  it('collapses bare log lines into one collapsed panel and keeps the answer clean', () => {
    const result = replaceAgenticLogsToSection(
      '[Agentic RAG] Starting research...\n[Keywords] 1.5mm^2\nHere is the answer.',
      'Log · {{num}}',
    );

    expect(result).toContain('<details class="agentic-log">');
    expect(result).toContain('<summary>Log · 2</summary>');
    expect(result).toContain('`[Keywords]` 1.5mm^2');
    expect(result).toContain('Here is the answer.');
    // The raw log lines must not survive outside the collapsed panel.
    expect(result).not.toContain('\n[Agentic RAG]');
  });

  it('extracts untagged tool chatter along with the tagged stages', () => {
    const result = replaceAgenticLogsToSection(
      'Running the rag tool...\n[Keywords] cable\nRunning tool...\nThe answer.',
      'Log · {{num}}',
    );

    expect(result).toContain('<summary>Log · 3</summary>');
    expect(result).toContain('Running the rag tool...');
    expect(result).toContain('Running tool...');
    expect(result).toContain('The answer.');
    expect(result.startsWith('<details')).toBe(true);
  });

  it('recognises the extra stage tags the pipeline forwards', () => {
    expect(isAgenticLogLine('[Memory] recall 2 hits')).toBe(true);
    expect(isAgenticLogLine('[Composing the answer] drafting')).toBe(true);
    expect(isAgenticPreambleLine('Running the rag tool...')).toBe(true);
    expect(isAgenticPreambleLine('Running tools')).toBe(true);
    // A real sentence that merely starts with those words is not chatter.
    expect(isAgenticPreambleLine('Running tools requires Python 3.13')).toBe(
      false,
    );
  });

  it('never extracts a line that carries a figure, image or citation', () => {
    const content = [
      '[Hybrid search] found the assembly drawing ![cable section](/img/a.png)',
      '[Keywords] see Fig. 1 for the conductor layout',
      '[Direct search] citation [ID:3] must stay visible',
      '[Memory] plain log line',
    ].join('\n');

    const result = replaceAgenticLogsToSection(content, 'Log · {{num}}');

    // Only the plain log line is collapsed; everything user-facing stays put.
    expect(result).toContain('<summary>Log · 1</summary>');
    expect(result).toContain('![cable section](/img/a.png)');
    expect(result).toContain('see Fig. 1 for the conductor layout');
    expect(result).toContain('[ID:3] must stay visible');
  });

  it('cleans the residue extraction leaves around the answer', () => {
    const result = replaceAgenticLogsToSection(
      '<br><br>[Keywords] cable\n<p></p>\nThe answer.',
      'Log · {{num}}',
    );

    expect(result.startsWith('<details')).toBe(true);
    expect(result).toContain('The answer.');
    expect(result).not.toMatch(/^<br/);
  });

  it('leaves fenced code blocks untouched', () => {
    const content = '```\n[Keywords] is not a log here\n```\nDone.';
    expect(replaceAgenticLogsToSection(content, 'Log · {{num}}')).toBe(content);
  });

  it('extracts <br>-separated logs that were never wrapped in a think block', () => {
    const result = replaceAgenticLogsToSection(
      '[Hybrid search] Searching for "x"<br>[Keywords] copper<br>The conductor is 1.5mm^2.',
      'Log · {{num}}',
    );

    expect(result).toContain('<summary>Log · 2</summary>');
    expect(result).toContain('`[Keywords]` copper');
    expect(result).toContain('The conductor is 1.5mm^2.');
  });

  it('keeps the answer text of a line that mixes a log with content', () => {
    const result = replaceAgenticLogsToSection(
      '[Keywords] copper<br>Answer paragraph.',
      'Log · {{num}}',
    );

    expect(result).toContain('<summary>Log · 1</summary>');
    expect(result).toContain('Answer paragraph.');
  });

  it('returns the input unchanged when there is nothing to extract', () => {
    expect(replaceAgenticLogsToSection('Just the answer.', 'Log')).toBe(
      'Just the answer.',
    );
  });

  it('recognises the stage tags the completed whitelist adds', () => {
    // Seven tags used to be listed while the pipeline emitted twenty-odd, so the
    // missing ones leaked into the answer body as raw text.
    for (const line of [
      '[SCA] sufficiency check round 2',
      '[QueryRewriter] 护套 PUR 紫色',
      '[SlotResearch] slot table after round:',
      '[Planner] 3 sub-questions',
      '[Routing] dataset route',
      '[Draft] draft v1',
      '[StateGuard] state trimmed',
      '[Follow-up search] 弯曲半径',
      '[Tool loop] iteration 2',
      '[Function tool] rag',
    ]) {
      expect(isAgenticLogLine(line)).toBe(true);
    }
  });

  it('collapses an unknown bracketed stage tag instead of leaking it', () => {
    // A stage added later must not leak just because nobody extended the list.
    expect(isAgenticLogLine('[Brand new stage] doing work')).toBe(true);
    expect(
      replaceAgenticLogsToSection(
        '[Brand new stage] doing work\nThe answer.',
        'Log · {{num}}',
      ),
    ).toContain('<summary>Log · 1</summary>');
  });

  it('does not mistake an evidence index or a markdown link for a stage tag', () => {
    // `[1]` is a footnote/evidence index the answer must keep.
    expect(isAgenticLogLine('[1]')).toBe(false);
    expect(isAgenticLogLine('[12] 0.0991 Ω/km')).toBe(false);
    // A bracketed link text is followed by `(`, not by answer text.
    expect(isAgenticLogLine('[见附表](https://example.com)')).toBe(false);
  });

  it('absorbs the continuation rows of a multi-line log record', () => {
    // `"[SlotResearch] slot table after round:\n%s"` prints its body on the
    // following lines, which carry no tag of their own.
    const result = replaceAgenticLogsToSection(
      [
        '[SlotResearch] slot table after round:',
        '| slot | value |',
        '| --- | --- |',
        '| 护套 | PUR 紫色 |',
        'The answer.',
      ].join('\n'),
      'Log · {{num}}',
    );

    expect(result).toContain('<summary>Log · 4</summary>');
    expect(result).toContain('| 护套 | PUR 紫色 |');
    expect(result).toContain('The answer.');
  });

  it('ends the log run at the first line that is not a continuation', () => {
    // The answer follows the last log line with no separator, so a broad
    // "everything after a log line is a log line" rule would swallow it.
    const result = replaceAgenticLogsToSection(
      [
        '[SlotResearch] slot table after round:',
        '| slot | value |',
        '护套为 PUR 紫色，外径 6.60 mm。',
        '- 弯曲半径 5 倍',
      ].join('\n'),
      'Log · {{num}}',
    );

    expect(result).toContain('<summary>Log · 2</summary>');
    expect(result).toContain('护套为 PUR 紫色，外径 6.60 mm。');
    expect(result).toContain('- 弯曲半径 5 倍');
  });

  it('never absorbs a continuation line that carries a citation', () => {
    // Same veto as for tagged lines: hiding a citation damages the answer.
    expect(isAgenticLogContinuation('| [ID:2] | 0.0991 |')).toBe(false);

    const result = replaceAgenticLogsToSection(
      '[SlotResearch] slot table after round:\n| [ID:2] | 0.0991 |\nThe answer.',
      'Log · {{num}}',
    );

    expect(result).toContain('<summary>Log · 1</summary>');
    expect(result).toContain('| [ID:2] | 0.0991 |');
  });

  it('classifies only table, indented and box-drawing continuations', () => {
    expect(isAgenticLogContinuation('| slot | value |')).toBe(true);
    expect(isAgenticLogContinuation('  indented body')).toBe(true);
    expect(isAgenticLogContinuation('\t\tindented body')).toBe(true);
    // A single leading whitespace is answer markdown (an indented code block),
    // not a log continuation.
    expect(isAgenticLogContinuation('\tindented body')).toBe(false);
    expect(isAgenticLogContinuation(' indented body')).toBe(false);
    expect(isAgenticLogContinuation('│ box drawing')).toBe(true);
    expect(isAgenticLogContinuation('')).toBe(false);
    expect(isAgenticLogContinuation('   ')).toBe(false);
    expect(isAgenticLogContinuation('- 弯曲半径 5 倍')).toBe(false);
    expect(isAgenticLogContinuation('普通答案正文。')).toBe(false);
  });
});

describe('promoteCaretExponentsToLaTeX', () => {
  it('promotes cable-unit exponents typed as plain text', () => {
    expect(promoteCaretExponentsToLaTeX('1.5mm^2 conductor')).toBe(
      '1.5mm$^{2}$ conductor',
    );
    expect(promoteCaretExponentsToLaTeX('10^-6 m^3')).toBe(
      '10$^{-6}$ m$^{3}$',
    );
    expect(promoteCaretExponentsToLaTeX('m^{3}/s')).toBe('m$^{3}$/s');
  });

  it('does not touch code spans, fenced code or existing math', () => {
    expect(promoteCaretExponentsToLaTeX('use `x^2` here')).toBe(
      'use `x^2` here',
    );
    expect(promoteCaretExponentsToLaTeX('$a^2 + b^2$')).toBe('$a^2 + b^2$');
    expect(promoteCaretExponentsToLaTeX('```\nx^2\n```')).toBe('```\nx^2\n```');
  });

  it('leaves text without a caret untouched', () => {
    expect(promoteCaretExponentsToLaTeX('plain text')).toBe('plain text');
  });
});

describe('trimExtractionResidue', () => {
  it('strips the line breaks and empty paragraphs left around the answer', () => {
    expect(trimExtractionResidue('<br><br>\n<p></p>\n<details>x</details>\n\n')).toBe(
      '<details>x</details>',
    );
  });

  it('leaves real content alone', () => {
    expect(trimExtractionResidue('1.5mm^2 conductor')).toBe('1.5mm^2 conductor');
  });
});

describe('conversation id provenance', () => {
  it('marks generated placeholder ids as temporary', () => {
    const conversationId = generateTemporaryConversationId();

    expect(conversationId).toMatch(/^temp-[0-9a-f]{32}$/);
    expect(isTemporaryConversationId(conversationId)).toBe(true);
    expect(isPersistedConversationId(conversationId)).toBe(false);
  });

  it('treats server ids as persisted', () => {
    const serverId = '014e4f2aab7911f191ac3887d563fb04';

    expect(isTemporaryConversationId(serverId)).toBe(false);
    expect(isPersistedConversationId(serverId)).toBe(true);
  });

  it('treats a missing id as neither temporary nor persisted', () => {
    expect(isTemporaryConversationId('')).toBe(false);
    expect(isTemporaryConversationId(undefined)).toBe(false);
    expect(isPersistedConversationId('')).toBe(false);
    expect(isPersistedConversationId(undefined)).toBe(false);
  });
});

describe('conversation list order', () => {
  /** Only the three fields the order reads are meaningful here. */
  const buildConversation = (
    id: string,
    updateTime: number,
    isPinned = false,
  ) =>
    ({
      id,
      update_time: updateTime,
      is_pinned: isPinned,
    }) as IConversation;

  const readIds = (list: IConversation[]) => list.map((item) => item.id);

  const list = [
    buildConversation('older', 100),
    buildConversation('newest', 300),
    buildConversation('middle', 200),
  ];

  it('puts the most recent conversation first', () => {
    expect(readIds(orderConversations(list))).toEqual([
      'newest',
      'middle',
      'older',
    ]);
  });

  it('keeps pinned conversations above a more recent one', () => {
    const withPin = [...list, buildConversation('pinned', 50, true)];

    expect(readIds(orderConversations(withPin))).toEqual([
      'pinned',
      'newest',
      'middle',
      'older',
    ]);
  });

  it('orders pinned conversations among themselves by activity', () => {
    const withPins = [
      buildConversation('pinned-old', 10, true),
      buildConversation('pinned-new', 20, true),
      buildConversation('plain', 999),
    ];

    expect(readIds(orderConversations(withPins))).toEqual([
      'pinned-new',
      'pinned-old',
      'plain',
    ]);
  });

  it('bumps a conversation to the top of the unpinned group', () => {
    expect(readIds(bumpConversation(list, 'older', 400))).toEqual([
      'older',
      'newest',
      'middle',
    ]);
  });

  it('does not bump a conversation above the pinned ones', () => {
    const withPin = [...list, buildConversation('pinned', 50, true)];

    expect(readIds(bumpConversation(withPin, 'older', 400))).toEqual([
      'pinned',
      'older',
      'newest',
      'middle',
    ]);
  });

  it('pins a conversation without touching its neighbours', () => {
    expect(readIds(pinConversation(list, 'older', true))).toEqual([
      'older',
      'newest',
      'middle',
    ]);
  });

  it('returns an unpinned conversation to its activity position', () => {
    const pinned = pinConversation(list, 'older', true);

    expect(readIds(pinConversation(pinned, 'older', false))).toEqual([
      'newest',
      'middle',
      'older',
    ]);
  });

  it('leaves the list it was given untouched', () => {
    const input = [...list];

    bumpConversation(input, 'older', 400);
    pinConversation(input, 'older', true);

    expect(readIds(input)).toEqual(['older', 'newest', 'middle']);
    expect(input[0].update_time).toBe(100);
    expect(input[0].is_pinned).toBe(false);
  });
});
