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

export const normalizeCitationDigits = (text: string) => {
  if (!text) return text;
  return text.replace(/[٠-٩۰-۹]/g, (char) => {
    const code = char.charCodeAt(0);
    if (code >= 0x0660 && code <= 0x0669) {
      return String.fromCharCode(code - 0x0660 + 0x30);
    }
    if (code >= 0x06f0 && code <= 0x06f9) {
      return String.fromCharCode(code - 0x06f0 + 0x30);
    }
    return char;
  });
};

/**
 * The raw number carried by a citation marker.
 *
 * Returns the number from `[ID:N]` / `[N]` (Arabic-Indic digits normalized), or
 * `NaN` when the text carries no marker. Do NOT use as array index directly:
 * this is the number the backend printed next to the evidence block, and the
 * chat and agentic flows print it 1-based (`kb_prompt` renders "ID: 1" … "ID: n",
 * see rag/prompts/generator.py), so `[ID:5]` refers to the array element at
 * index 4. The search/ask flow instead emits already-0-based markers
 * (rag/nlp/search.py:insert_citations) and is the one caller that indexes with
 * this value directly.
 */
export const parseCitationIndex = (value: string) => {
  const normalized = normalizeCitationDigits(value);
  const markerMatch = normalized.match(/\[(?:ID:)?(\d+)\]/);
  if (markerMatch) return Number(markerMatch[1]);
  if (/^\d+$/.test(normalized)) return Number(normalized);
  return Number.NaN;
};

/**
 * The 0-based array index of the chunk a citation marker points at.
 *
 * Returns 0-based array index for chat/agentic flows (1-based kb_prompt
 * numbering): `[ID:1]` → 0, `[ID:5]` → 4. Returns `NaN` for a malformed or
 * absent marker, for `[ID:0]` (not a valid 1-based citation) and — when
 * `poolSize` is supplied — for an index outside `[0, poolSize)`, so a caller
 * can skip rendering instead of reading `undefined` out of the chunk pool.
 *
 * Do NOT use this for the search/ask flow: its markers are already 0-based, so
 * `pages/next-search` must keep using `parseCitationIndex`.
 */
export const citedChunkIndex = (value: string, poolSize?: number) => {
  // Guarded before parsing: callers pass values that may be undefined when a
  // reference pool is missing, and this function must report "no index" rather
  // than throw.
  if (typeof value !== 'string') return Number.NaN;
  const index = parseCitationIndex(value) - 1;
  if (Number.isNaN(index) || index < 0) return Number.NaN;
  if (typeof poolSize === 'number' && index >= poolSize) return Number.NaN;
  return index;
};

export const citationMarkerReg =
  /\[(?:ID:)?([0-9\u0660-\u0669\u06F0-\u06F9]+)\]/g;
