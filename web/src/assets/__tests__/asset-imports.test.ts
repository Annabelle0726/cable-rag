/*
 *  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

import fs from 'fs';
import path from 'path';

/**
 * Every asset an import names has to exist.
 *
 * TypeScript cannot catch this: `vite-env.d.ts` declares `*.jpg`/`*.png` as
 * ambient wildcard modules, so `import poster from '@/assets/icon/gone.jpg'`
 * type-checks happily whether or not the file is there. Only the bundler
 * resolves the real path, which turns a renamed or deleted asset into a
 * dev-server 500 on the module that imports it - surfacing as
 * "Failed to fetch dynamically imported module" on whichever lazy route
 * happened to pull that module in, with the real culprit named nowhere.
 */

const SRC = path.resolve(__dirname, '..', '..');
const ASSET_EXTENSIONS = /\.(png|jpe?g|gif|svg|webp|ico|mp4|webm|woff2?|ttf|otf)$/i;
const IMPORT_RE = /(?:from|import)\s*\(?\s*['"]([^'"]+)['"]/g;
// Comments carry examples and old paths; matching them reports files nobody
// imports. `routes.tsx` keeps a commented-out route, which is what made a
// naive scan blame a page that is not in the graph at all.
const COMMENT_RE = /\/\*[\s\S]*?\*\/|\/\/[^\n]*/g;
const SOURCE_EXTENSIONS = ['.ts', '.tsx'];

const sourceFiles = (dir: string): string[] =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      return entry.name === '__tests__' ? [] : sourceFiles(full);
    }
    return SOURCE_EXTENSIONS.includes(path.extname(entry.name)) ? [full] : [];
  });

const resolveAsset = (fromFile: string, specifier: string): string | null => {
  const base = specifier.startsWith('@/')
    ? path.join(SRC, specifier.slice(2))
    : specifier.startsWith('.')
      ? path.join(path.dirname(fromFile), specifier)
      : null;
  return base;
};

describe('asset imports resolve', () => {
  it('every imported asset exists on disk', () => {
    const missing: string[] = [];

    for (const file of sourceFiles(SRC)) {
      const source = fs.readFileSync(file, 'utf8').replace(COMMENT_RE, '');
      for (const match of source.matchAll(IMPORT_RE)) {
        const specifier = match[1];
        if (!ASSET_EXTENSIONS.test(specifier)) continue;
        const resolved = resolveAsset(file, specifier);
        if (resolved && !fs.existsSync(resolved)) {
          missing.push(
            `${path.relative(SRC, file)} imports ${specifier} (not on disk)`,
          );
        }
      }
    }

    expect(missing).toEqual([]);
  });
});
