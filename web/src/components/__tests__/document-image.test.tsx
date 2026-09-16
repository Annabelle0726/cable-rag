import Image from '@/components/image';
import { render, screen, waitFor } from '@testing-library/react';

// The reference images used to fail silently: the request was rejected with 401
// (an empty Authorization header stops the backend from falling back to the
// session cookie), the component rendered an <img> with no src, and the reader
// saw an empty box with just the 图 label.
describe('document image', () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    window.localStorage.clear();
  });

  it('sends the session cookie and no empty Authorization header', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(['image'])),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<Image id="kb-chunk" label="Fig. 5" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/documents/images/kb-chunk');
    expect(init.credentials).toBe('same-origin');
    expect(init.headers).toBeUndefined();
  });

  it('forwards a stored token as a bearer header', async () => {
    window.localStorage.setItem('Authorization', 'Bearer token-value');
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(['image'])),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<Image id="kb-chunk-2" label="Fig. 6" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    expect(fetchMock.mock.calls[0][1].headers).toEqual({
      Authorization: 'Bearer token-value',
    });
  });

  it('says so on screen when the image cannot be loaded', async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
    }) as unknown as typeof fetch;

    render(<Image id="kb-chunk-3" label="Fig. 7" />);

    expect(await screen.findByTestId('image-load-failed')).toBeInTheDocument();
    expect(screen.getByText('Fig. 7')).toBeInTheDocument();
  });
});
