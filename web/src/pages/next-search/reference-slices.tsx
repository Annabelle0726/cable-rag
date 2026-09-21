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

import { FileIcon } from '@/components/icon-font';
import { ImageWithPopover } from '@/components/image';
import { Button } from '@/components/ui/button';
import { ITestingChunk } from '@/interfaces/database/dataset';
import { sanitizeHtmlWithImagesAsText } from '@/utils/dom-util';
import classNames from 'classnames';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * How many passages the result page opens with.
 *
 * The retrieval list is evidence for the answer above it, not a corpus dump: a
 * tuned search returns a dozen passages of which the reader checks the first
 * few, and rendering all of them pushed the related-search links and the
 * pagination summary off the first screen. The rest stay one click away, and
 * the count shown on the button says how many that is.
 */
const VISIBLE_SLICE_COUNT = 5;

const formatMetadataValue = (value: unknown) => {
  if (Array.isArray(value)) return value.join(', ');
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

interface ReferenceSlicesProps {
  chunks: ITestingChunk[];
  onOpenDocument: (documentId: string, chunk: ITestingChunk) => void;
}

export default function ReferenceSlices({
  chunks,
  onOpenDocument,
}: ReferenceSlicesProps) {
  const { t } = useTranslation();
  const [visibleCount, setVisibleCount] = useState(VISIBLE_SLICE_COUNT);

  // A new search brings a new list, so the list collapses back to its opening
  // length instead of keeping the previous query's expansion.
  useEffect(() => {
    setVisibleCount(VISIBLE_SLICE_COUNT);
  }, [chunks]);

  const handleExpand = useCallback(() => {
    setVisibleCount(chunks.length);
  }, [chunks.length]);

  const handleCollapse = useCallback(() => {
    setVisibleCount(VISIBLE_SLICE_COUNT);
  }, []);

  const isExpanded = visibleCount >= chunks.length;

  return (
    <div className="mt-3" data-testid="reference-slices">
      {chunks.slice(0, visibleCount).map((chunk, index) => (
        <div key={chunk.id ?? index} data-testid="reference-slice">
          <div className="w-full flex flex-col">
            <div className="w-full">
              {chunk.image_id && <ImageWithPopover id={chunk.image_id} />}
              <div
                dangerouslySetInnerHTML={{
                  __html: sanitizeHtmlWithImagesAsText(
                    chunk.highlight || chunk.content,
                  ).trim(),
                }}
                className={classNames(
                  'text-wrap break-words whitespace-pre text-base',
                  '[&_em]:text-accent-primary [&_em]:not-italic',
                )}
              />
            </div>
            {chunk.document_metadata &&
              Object.keys(chunk.document_metadata).length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {Object.entries(chunk.document_metadata).map(
                    ([key, value]) => (
                      <div
                        key={key}
                        className="text-xs border border-border-default rounded px-2 py-1"
                      >
                        <span className="text-text-secondary">{key}:</span>{' '}
                        <span className="text-text-primary">
                          {formatMetadataValue(value)}
                        </span>
                      </div>
                    ),
                  )}
                </div>
              )}
            <div
              className="flex gap-2 items-center text-xs text-text-secondary border p-1 rounded-lg w-fit mt-3 cursor-pointer"
              onClick={() => onOpenDocument(chunk.document_id, chunk)}
            >
              <FileIcon name={chunk.document_keyword}></FileIcon>
              {chunk.document_keyword}
            </div>
          </div>
          {index < visibleCount - 1 && (
            <div className="w-full border-b border-border-default/80 mt-6 mb-2"></div>
          )}
        </div>
      ))}

      {chunks.length > VISIBLE_SLICE_COUNT && (
        <div className="flex justify-center">
          <Button
            variant="outline"
            className="gap-1.5"
            onClick={isExpanded ? handleCollapse : handleExpand}
            data-testid="reference-slices-toggle"
          >
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            <span>
              {isExpanded
                ? t('search.collapseSlices')
                : t('search.expandSlices', {
                    count: chunks.length - VISIBLE_SLICE_COUNT,
                  })}
            </span>
          </Button>
        </div>
      )}
    </div>
  );
}
