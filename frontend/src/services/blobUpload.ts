import { UPLOAD_BLOCK_CONCURRENCY, UPLOAD_BLOCK_SIZE, UPLOAD_SINGLE_SHOT_LIMIT } from '@/config';

/**
 * Direct-to-storage upload, step 2 of the two-step flow.
 *
 * The bytes never touch the API: the browser PUTs them straight to the
 * presigned (SAS) URL. Small files go up in a single request; anything past
 * UPLOAD_SINGLE_SHOT_LIMIT is staged as blocks and committed with a block list,
 * so a dropped connection at 48/50 MB retries one block instead of the file.
 *
 * No Authorization header is ever attached here — the SAS token in the URL is
 * the credential, and sending a bearer token to storage would be rejected.
 */

export interface UploadOptions {
  uploadUrl: string;
  file: File;
  signal?: AbortSignal;
  onProgress?: (percent: number, uploadedBytes: number) => void;
}

export async function uploadToPresignedUrl(options: UploadOptions): Promise<void> {
  const { file } = options;
  if (file.size <= UPLOAD_SINGLE_SHOT_LIMIT) {
    await singleShotUpload(options);
    return;
  }
  await blockUpload(options);
}

function contentTypeOf(file: File): string {
  return file.type || 'application/octet-stream';
}

/** XHR rather than fetch: it is the only way to get real upload progress. */
function putWithProgress(
  url: string,
  body: Blob,
  headers: Record<string, string>,
  signal: AbortSignal | undefined,
  onProgress?: (loaded: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', url, true);
    for (const [key, value] of Object.entries(headers)) xhr.setRequestHeader(key, value);

    const abort = () => xhr.abort();
    signal?.addEventListener('abort', abort);

    const cleanup = () => signal?.removeEventListener('abort', abort);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(event.loaded);
    };
    xhr.onload = () => {
      cleanup();
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error(storageError(xhr.status, xhr.responseText)));
    };
    xhr.onerror = () => {
      cleanup();
      reject(new Error('Network error while uploading to storage'));
    };
    xhr.onabort = () => {
      cleanup();
      reject(new DOMException('Upload cancelled', 'AbortError'));
    };

    xhr.send(body);
  });
}

function storageError(status: number, responseText: string): string {
  const code = /<Code>([^<]+)<\/Code>/.exec(responseText)?.[1];
  if (code === 'AuthenticationFailed') return 'The upload link expired. Try the upload again.';
  return code ? `Storage rejected the upload (${status}: ${code})` : `Storage rejected the upload (${status})`;
}

async function singleShotUpload({ uploadUrl, file, signal, onProgress }: UploadOptions): Promise<void> {
  await putWithProgress(
    uploadUrl,
    file,
    { 'x-ms-blob-type': 'BlockBlob', 'Content-Type': contentTypeOf(file) },
    signal,
    (loaded) => onProgress?.(Math.round((loaded / file.size) * 100), loaded),
  );
  onProgress?.(100, file.size);
}

async function blockUpload({ uploadUrl, file, signal, onProgress }: UploadOptions): Promise<void> {
  const blockCount = Math.ceil(file.size / UPLOAD_BLOCK_SIZE);
  const blockIds = Array.from({ length: blockCount }, (_, index) => encodeBlockId(index));
  const uploadedPerBlock = new Array<number>(blockCount).fill(0);

  const reportProgress = () => {
    const uploaded = uploadedPerBlock.reduce((sum, value) => sum + value, 0);
    onProgress?.(Math.min(99, Math.round((uploaded / file.size) * 100)), uploaded);
  };

  let nextBlock = 0;
  const worker = async (): Promise<void> => {
    while (nextBlock < blockCount) {
      const index = nextBlock++;
      if (signal?.aborted) throw new DOMException('Upload cancelled', 'AbortError');

      const start = index * UPLOAD_BLOCK_SIZE;
      const chunk = file.slice(start, Math.min(start + UPLOAD_BLOCK_SIZE, file.size));

      await withRetry(
        () =>
          putWithProgress(
            appendQuery(uploadUrl, { comp: 'block', blockid: blockIds[index] }),
            chunk,
            { 'Content-Type': 'application/octet-stream' },
            signal,
            (loaded) => {
              uploadedPerBlock[index] = loaded;
              reportProgress();
            },
          ),
        signal,
      );

      uploadedPerBlock[index] = chunk.size;
      reportProgress();
    }
  };

  const workers = Array.from({ length: Math.min(UPLOAD_BLOCK_CONCURRENCY, blockCount) }, worker);
  await Promise.all(workers);

  // Commit: the blob only becomes visible once the block list is written.
  const body = blockListXml(blockIds);
  await withRetry(
    () =>
      putWithProgress(
        appendQuery(uploadUrl, { comp: 'blocklist' }),
        new Blob([body], { type: 'application/xml' }),
        { 'x-ms-blob-content-type': contentTypeOf(file) },
        signal,
      ),
    signal,
  );

  onProgress?.(100, file.size);
}

/** Block ids must be equal-length and base64 encoded. */
function encodeBlockId(index: number): string {
  return btoa(`block-${String(index).padStart(8, '0')}`);
}

function blockListXml(blockIds: string[]): string {
  const latest = blockIds.map((id) => `<Latest>${id}</Latest>`).join('');
  return `<?xml version="1.0" encoding="utf-8"?><BlockList>${latest}</BlockList>`;
}

function appendQuery(url: string, params: Record<string, string>): string {
  const parsed = new URL(url);
  for (const [key, value] of Object.entries(params)) parsed.searchParams.set(key, value);
  return parsed.toString();
}

async function withRetry<T>(operation: () => Promise<T>, signal?: AbortSignal, attempts = 3): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await operation();
    } catch (error) {
      if (signal?.aborted || (error as Error)?.name === 'AbortError') throw error;
      lastError = error;
      await delay(2 ** attempt * 500);
    }
  }
  throw lastError;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
