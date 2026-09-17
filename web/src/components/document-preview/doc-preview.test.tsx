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

jest.mock('./pdf-preview', () => ({
  __esModule: true,
  default: ({ url }: { url: string }) => (
    <div data-testid="pdf-previewer" data-url={url} />
  ),
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

const mockFetchedBlob = (bytes: number[]): Blob =>
  new Blob([new Uint8Array(bytes)]);

// jsdom's Blob has no arrayBuffer(), and the previewer reads the header of both
// the payload and a slice of the conversion response. Shimming the prototype
// (rather than one instance) keeps slice() results readable too, and the value
// stays a real Blob so it can still be wrapped in a File.
const shimBlobArrayBuffer = () => {
  if (typeof Blob.prototype.arrayBuffer === 'function') {
    return;
  }

  Object.defineProperty(Blob.prototype, 'arrayBuffer', {
    configurable: true,
    writable: true,
    value: function arrayBuffer(this: Blob): Promise<ArrayBuffer> {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as ArrayBuffer);
        reader.onerror = () => reject(reader.error);
        reader.readAsArrayBuffer(this);
      });
    },
  });
};

beforeAll(() => {
  shimBlobArrayBuffer();
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
  // The conversion endpoint answers with the original bytes when LibreOffice is
  // missing, which is the case this asserts.
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

  // With LibreOffice installed the server exports the legacy file, and the PDF
  // viewer takes over from the notice.
  it('renders the server-converted PDF for a legacy Word file', async () => {
    mockDetectedFormat = 'legacy-office';
    MockRequest.mockImplementation((async (requestUrl: string) =>
      requestUrl.includes('format=pdf')
        ? { data: mockFetchedBlob([0x25, 0x50, 0x44, 0x46]) }
        : {
            data: mockFetchedBlob([
              0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1,
            ]),
          }) as never);

    render(<DocPreviewer url="http://example.com/document.doc" />);

    await waitFor(() => {
      expect(screen.getByTestId('pdf-previewer')).toBeInTheDocument();
    });
    expect(screen.getByTestId('pdf-previewer')).toHaveAttribute(
      'data-url',
      'http://example.com/document.doc?format=pdf',
    );
    expect(
      screen.queryByTestId('doc-preview-notice-message'),
    ).not.toBeInTheDocument();
  });

  // A JSON error body (or any non-PDF payload) must not reach the PDF viewer.
  it('keeps the notice when the conversion is not a PDF', async () => {
    mockDetectedFormat = 'legacy-office';
    MockRequest.mockImplementation((async (requestUrl: string) =>
      requestUrl.includes('format=pdf')
        ? { data: mockFetchedBlob([0x7b, 0x22, 0x63, 0x6f]) }
        : {
            data: mockFetchedBlob([
              0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1,
            ]),
          }) as never);

    render(<DocPreviewer url="http://example.com/document.doc" />);

    await waitFor(() => {
      expect(screen.getByTestId('doc-preview-notice-message')).toHaveTextContent(
        /Word 97-2003/,
      );
    });
    expect(screen.queryByTestId('pdf-previewer')).not.toBeInTheDocument();
  });
});
