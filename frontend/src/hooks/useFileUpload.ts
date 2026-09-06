import { useCallback, useRef, useState } from 'react';
import { uid } from '@/lib/format';
import { uploadToPresignedUrl } from '@/services/blobUpload';
import { requestUploadUrl } from '@/services/files';
import type { MessageAttachment, PendingAttachment } from '@/types';

/**
 * Composer attachments.
 *
 * Picking a file stages the bytes straight away — ask the API for a SAS URL,
 * then PUT to storage, so a 50MB PDF is already in place by the time the user
 * finishes typing and the send feels instant.
 *
 * Staging is deliberately not the same thing as acting. Nothing reaches the
 * SharePoint library here: the `fileId` rides along with the chat message, and
 * the agent decides whether it is a new document, a replacement or an update —
 * and comes back for confirmation if it is destructive.
 */
export function useFileUpload() {
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const controllersRef = useRef<Map<string, AbortController>>(new Map());

  const patch = useCallback((id: string, changes: Partial<PendingAttachment>) => {
    setAttachments((current) =>
      current.map((item) => (item.id === id ? { ...item, ...changes } : item)),
    );
  }, []);

  const attachFile = useCallback(
    async (file: File) => {
      const id = uid('attachment');
      setAttachments((current) => [
        ...current,
        { id, fileName: file.name, size: file.size, phase: 'requesting-url', progress: 0 },
      ]);

      const controller = new AbortController();
      controllersRef.current.set(id, controller);

      try {
        const target = await requestUploadUrl({
          fileName: file.name,
          contentType: file.type || 'application/pdf',
          size: file.size,
        });

        patch(id, { phase: 'uploading', progress: 0 });

        await uploadToPresignedUrl({
          uploadUrl: target.uploadUrl,
          file,
          signal: controller.signal,
          onProgress: (percent) => patch(id, { progress: percent }),
        });

        patch(id, {
          phase: 'ready',
          progress: 100,
          fileId: target.fileId,
          blobPath: target.blobPath,
        });
      } catch (error) {
        if ((error as Error)?.name === 'AbortError') {
          patch(id, { phase: 'cancelled' });
        } else {
          patch(id, {
            phase: 'error',
            error: error instanceof Error ? error.message : 'Upload failed',
          });
        }
      } finally {
        controllersRef.current.delete(id);
      }

      return id;
    },
    [patch],
  );

  const removeAttachment = useCallback((id: string) => {
    controllersRef.current.get(id)?.abort();
    controllersRef.current.delete(id);
    setAttachments((current) => current.filter((item) => item.id !== id));
  }, []);

  /** Called once a message carrying these attachments has been sent. */
  const clearAttachments = useCallback(() => {
    for (const controller of controllersRef.current.values()) controller.abort();
    controllersRef.current.clear();
    setAttachments([]);
  }, []);

  return { attachments, attachFile, removeAttachment, clearAttachments };
}

/** Only staged files can be sent; anything still uploading or failed is dropped. */
export function toMessageAttachments(attachments: PendingAttachment[]): MessageAttachment[] {
  return attachments
    .filter((item) => item.phase === 'ready')
    .map((item) => ({
      fileId: item.fileId,
      fileName: item.fileName,
      size: item.size,
      blobPath: item.blobPath,
    }));
}
