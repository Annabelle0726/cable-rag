import fs from 'fs';
import path from 'path';

const webRoot = path.resolve(__dirname, '../..');
const css = fs.readFileSync(path.join(webRoot, 'tailwind.css'), 'utf8');

/**
 * A theme token can be spelled two ways and they are not interchangeable:
 * `--x: 220 14% 16%` is an `hsl()` triple meant for `hsl(var(--x))`, while
 * `--x: 35 39 47` is an RGB channel triple meant for `rgb(var(--x))`. Feeding
 * the first to `rgb()` is NOT a syntax error a browser drops - it resolves
 * channel-wise, so `rgb(220 14% 16%)` paints `rgb(220, 36, 41)`, a saturated
 * red. That is exactly what `.dark`'s `--bg-canvas` did to the agent workflow
 * canvas, and nothing in the build or the type checker could see it.
 *
 * These tests derive the contract from the consumers rather than restating a
 * list, so a new `rgb(var(--token))` anywhere fails here until the token holds
 * channel numbers in both theme blocks.
 */
const RGB_TRIPLE = /^\d{1,3} \d{1,3} \d{1,3}$/;

const blockOf = (selector: string) => {
  const pattern = new RegExp(
    `^\\s*${selector.replace('.', '\\.')}\\s*\\{([\\s\\S]*?)^\\s*\\}`,
    'm',
  );
  const match = css.match(pattern);
  if (!match) throw new Error(`tailwind.css has no ${selector} block`);
  return match[1];
};

const declaredValue = (block: string, token: string) => {
  const match = block.match(new RegExp(`^\\s*--${token}\\s*:\\s*([^;]+);`, 'm'));
  return match ? match[1].trim() : null;
};

const sourceFiles = (dir: string): string[] =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    if (entry.name === 'node_modules' || entry.name.startsWith('.umi')) return [];
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    const isSource =
      /\.(ts|tsx|css|less)$/.test(entry.name) && !entry.name.endsWith('.d.ts');
    return isSource ? [full] : [];
  });

// Prose about the contract is not the contract: this file's own doc comment
// writes `rgb(var(--x))` as an example, and a scan that counts it derives a
// token named `x`.
const stripComments = (text: string) =>
  text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

const rgbConsumedTokens = () => {
  const files = [
    path.join(webRoot, 'tailwind.config.js'),
    ...sourceFiles(path.join(webRoot, 'src')),
  ];
  const tokens = new Set<string>();
  for (const file of files) {
    const text = stripComments(fs.readFileSync(file, 'utf8'));
    for (const match of text.matchAll(/rgb\(var\(--([a-z0-9-]+)/g)) {
      tokens.add(match[1]);
    }
  }
  return [...tokens].sort();
};

describe('theme token spelling', () => {
  const root = blockOf(':root');
  const dark = blockOf('.dark');
  const consumed = rgbConsumedTokens();

  it('finds the tokens the stylesheet feeds to rgb(var(...))', () => {
    // If this list ever comes back empty the derivation broke, and every
    // assertion below would pass vacuously.
    expect(consumed).toEqual(
      expect.arrayContaining([
        'accent-primary',
        'bg-canvas',
        'bg-list',
        'text-primary',
        'text-primary-inverse',
        'text-secondary',
      ]),
    );
  });

  it.each(consumed)(
    '--%s holds RGB channel numbers in every block that declares it',
    (token) => {
      const light = declaredValue(root, token);
      expect(light).not.toBeNull();
      expect(light).toMatch(RGB_TRIPLE);

      const darkValue = declaredValue(dark, token);
      if (darkValue !== null) expect(darkValue).toMatch(RGB_TRIPLE);
    },
  );

  it('keeps the canvas tokens off the hsl() spelling that painted the agent canvas red', () => {
    // The historical value: `--bg-canvas: 220 14% 16%` in `.dark`, which the
    // flow canvas computed to rgb(220, 36, 41) on /agent/<id>.
    expect(declaredValue(dark, 'bg-canvas')).toBe('35 39 47');
    expect(declaredValue(dark, 'bg-list')).toBe('42 46 55');
  });
});
