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

import JSZip from 'jszip';
import { detectOfficeFormat } from './office-format';

const packageWith = async (entries: string[]): Promise<ArrayBuffer> => {
  const zip = new JSZip();
  entries.forEach((entry) => zip.file(entry, '<xml/>'));

  return zip.generateAsync({ type: 'arraybuffer' });
};

/** A legacy Word 97-2003 file: the OLE2 compound-file header, nothing else. */
const legacyOfficeBytes = (): ArrayBuffer =>
  new Uint8Array([
    0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1, 0x00, 0x00, 0x00, 0x00,
  ]).buffer;

describe('detectOfficeFormat', () => {
  it('recognises a docx package', async () => {
    const data = await packageWith([
      '[Content_Types].xml',
      'word/document.xml',
      'word/styles.xml',
    ]);

    await expect(detectOfficeFormat(data)).resolves.toBe('docx');
  });

  it('recognises an xlsx package', async () => {
    const data = await packageWith(['[Content_Types].xml', 'xl/workbook.xml']);

    await expect(detectOfficeFormat(data)).resolves.toBe('xlsx');
  });

  it('recognises a pptx package', async () => {
    const data = await packageWith([
      '[Content_Types].xml',
      'ppt/presentation.xml',
    ]);

    await expect(detectOfficeFormat(data)).resolves.toBe('pptx');
  });

  it('reports the legacy Word 97-2003 container', async () => {
    await expect(detectOfficeFormat(legacyOfficeBytes())).resolves.toBe(
      'legacy-office',
    );
  });

  it('reports a ZIP that holds no Office part as unknown', async () => {
    const data = await packageWith(['notes/readme.txt']);

    await expect(detectOfficeFormat(data)).resolves.toBe('unknown');
  });

  it('reports a payload that is neither ZIP nor OLE2 as unknown', async () => {
    // "{\rtf" — an RTF document renamed to .doc.
    const data = new Uint8Array([0x7b, 0x5c, 0x72, 0x74, 0x66]).buffer;

    await expect(detectOfficeFormat(data)).resolves.toBe('unknown');
  });

  it('reports an empty payload as unknown instead of throwing', async () => {
    await expect(detectOfficeFormat(new ArrayBuffer(0))).resolves.toBe(
      'unknown',
    );
  });
});
