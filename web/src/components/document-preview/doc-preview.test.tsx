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

import request from '@/utils/request';
import { render, screen, waitFor } from '@testing-library/react';
import { DocPreviewer } from './doc-preview';

const mockImportDocxFile = jest.fn().mockResolvedValue(undefined);
let mockEditorImportDocxFile = mockImportDocxFile;
// Kept as a plain string: the suite's transformer rejects an imported type that
// is also used in a type annotation.
let mockDetectedFormat = 'docx';

jest.mock('@/utils/request', () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock('@/components/ui/message', () => ({
  __esModule: true,
  default: { error: jest.fn() },
}));

jest.mock('@/components/ui/spin', () => ({
  Spin: () => <div data-testid="spin" />,
}));

jest.mock('./office-format', () => ({
  detectOfficeFormat: jest.fn(() => Promise.resolve(mockDetectedFormat)),
}));

jest.mock('./excel-preview', () => ({
  ExcelCsvPreviewer: () => <div data-testid="excel-previewer" />,
}));

jest.mock('./ppt-preview', () => ({
  PptPreviewer: () => <div data-testid="ppt-previewer" />,
}));

jest.mock('./hooks', () => ({
  useDocumentResizeObserver: () => ({
    containerWidth: 800,
    setContainerRef: jest.fn(),
  }),
  useDocxPreviewZoom: () => ({
    zoomScale: 100,
    minZoom: 50,
    maxZoom: 200,
    handleZoomIn: jest.fn(),
    handleZoomOut: jest.fn(),
  }),
}));

jest.mock('@extend-ai/react-docx', () => ({
  DocxEditorViewer: ({
    pageVirtualization,
  }: {
    pageVirtualization?: { enabled?: boolean };
  }) => (
    <div
      data-testid="docx-viewer"
      data-page-virtualization={JSON.stringify(pageVirtualization)}
    />
  ),
  useDocxEditor: () => ({
    importDocxFile: mockEditorImportDocxFile,
    status: 'ready',
    totalPages: 2,
  }),
  useDocxPageLayout: () => ({ layout: { pageWidthPx: 800 } }),
  parseDocx: jest.fn(),
  packageToArrayBuffer: jest.fn(),
}));

const MockRequest = jest.mocked(request);
const OriginalResizeObserver = globalThis.ResizeObserver;

// jsdom's Blob has no arrayBuffer(), which the previewer uses to inspect the
// payload's header. The shim keeps the value a real Blob so the code can still
// wrap it in a File.
const mockFetchedBlob = (bytes: number[]): Blob => {
  const blob = new Blob([new Uint8Array(bytes)]);

  if (typeof blob.arrayBuffer !== 'function') {
    Object.defineProperty(blob, 'arrayBuffer', {
      value: async () => new Uint8Array(bytes).buffer,
    });
  }

  return blob;
};

beforeAll(() => {
  globalThis.ResizeObserver = jest.fn().mockImplementation(() => ({
    observe: jest.fn(),
    unobserve: jest.fn(),
    disconnect: jest.fn(),
  }));
});

afterAll(() => {
  globalThis.ResizeObserver = OriginalResizeObserver;
});

describe('DocPreviewer', () => {
  beforeEach(() => {
    mockEditorImportDocxFile = mockImportDocxFile;
    mockImportDocxFile.mockClear();
    mockImportDocxFile.mockImplementation(async () => {
      // Mimic @extend-ai/react-docx returning a new callback after import.
      mockEditorImportDocxFile = jest.fn().mockResolvedValue(undefined);
    });
    mockDetectedFormat = 'docx';
    MockRequest.mockResolvedValue({
      data: mockFetchedBlob([0x50, 0x4b, 0x03, 0x04]),
    } as never);
  });

  it('loads the document once even when importDocxFile identity changes', async () => {
    const { rerender } = render(
      <DocPreviewer url="http://example.com/document.docx" />,
    );

    await waitFor(() => {
      expect(mockImportDocxFile).toHaveBeenCalledTimes(1);
    });

    rerender(<DocPreviewer url="http://example.com/document.docx" />);

    await waitFor(() => {
      expect(screen.getByTestId('docx-viewer')).toBeInTheDocument();
    });
    expect(mockImportDocxFile).toHaveBeenCalledTimes(1);
  });

  it('disables internal DOCX page virtualization to avoid update loops', async () => {
    render(<DocPreviewer url="http://example.com/document.docx" />);

    await waitFor(() => {
      expect(screen.getByTestId('docx-viewer')).toBeInTheDocument();
    });

    expect(screen.getByTestId('docx-viewer')).toHaveAttribute(
      'data-page-virtualization',
      JSON.stringify({ enabled: false }),
    );
  });

  // A .doc in the dataset can be a Word 97-2003 file, which no browser renderer
  // can read: the user gets a sentence they can act on, not a library error.
  it('explains a legacy Word file instead of leaking the library error', async () => {
    mockDetectedFormat = 'legacy-office';

    render(<DocPreviewer url="http://example.com/document.doc" />);

    await waitFor(() => {
      expect(screen.getByTestId('doc-preview-notice-message')).toHaveTextContent(
        /Word 97-2003/,
      );
    });
    expect(mockImportDocxFile).not.toHaveBeenCalled();
    expect(screen.queryByTestId('docx-viewer')).not.toBeInTheDocument();
  });

  it('keeps a generic notice for a payload no renderer understands', async () => {
    mockDetectedFormat = 'unknown';

    render(<DocPreviewer url="http://example.com/document.doc" />);

    await waitFor(() => {
      expect(screen.getByTestId('doc-preview-notice-message')).toBeInTheDocument();
    });
    expect(screen.getByTestId('doc-preview-notice-title')).toBeInTheDocument();
    expect(screen.getByTestId('doc-preview-notice-message')).not.toHaveTextContent(
      /Word 97-2003/,
    );
  });

  // The stored record said Word, but the payload is a spreadsheet: route it to
  // the previewer that can render it rather than reporting a broken .docx.
  it('hands a spreadsheet payload to the Excel previewer', async () => {
    mockDetectedFormat = 'xlsx';

    render(<DocPreviewer url="http://example.com/cable_test_spec.xlsx" />);

    await waitFor(() => {
      expect(screen.getByTestId('excel-previewer')).toBeInTheDocument();
    });
    expect(mockImportDocxFile).not.toHaveBeenCalled();
    expect(
      screen.queryByTestId('doc-preview-notice-message'),
    ).not.toBeInTheDocument();
  });
});
