import '@testing-library/jest-dom';
import React from 'react';

// esbuild-jest compiles JSX with the classic runtime (React.createElement),
// while source files rely on the automatic runtime and never import React.
// Expose React globally so rendering components in tests works.
(globalThis as Record<string, unknown>).React = React;

// jsdom does not provide these, but react-router reads them at module scope
if (typeof globalThis.TextEncoder === 'undefined') {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { TextDecoder, TextEncoder } = require('node:util');
  Object.assign(globalThis, { TextDecoder, TextEncoder });
}

// jsdom exposes no web streams either, while eventsource-parser/stream builds a
// TransformStream at module scope and is pulled in by the chat hooks.
if (typeof globalThis.TransformStream === 'undefined') {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { TransformStream } = require('node:stream/web');
  Object.assign(globalThis, { TransformStream });
}

// Vite's import.meta.glob is rewritten to this stub by jest-esbuild-transformer.cjs
(globalThis as Record<string, unknown>).jestImportMetaGlob = () => ({});

// jsdom does not expose fetch; some modules call it at import time and
// handle the rejection themselves (e.g. utils/backend-runtime.ts)
if (typeof globalThis.fetch === 'undefined') {
  (globalThis as Record<string, unknown>).fetch = () =>
    Promise.reject(new Error('fetch is not available in tests'));
}

// jsdom exposes no ResizeObserver either, while every component that measures
// its own overflow uses one (the collapsible answer and reference bodies, the
// mind map's canvas container). A no-op observer is enough: jsdom lays nothing
// out, so there is no size to report.
if (typeof globalThis.ResizeObserver === 'undefined') {
  (globalThis as Record<string, unknown>).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
