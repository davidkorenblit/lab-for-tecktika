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

  const attachFile = useCallback((file: File) => {
    const id = uid('attachment');
    setAttachments((current) => [
      ...current,
      { id, file, fileName: file.name, size: file.size, phase: 'selected', progress: 0 },
    ]);
    return id;
  }, []);

  const uploadSingle = useCallback(
    async (item: PendingAttachment): Promise<MessageAttachment> => {
      if (item.phase === 'ready' && item.fileId) {
        return {
          fileId: item.fileId,
          fileName: item.fileName,
          size: item.size,
          blobPath: item.blobPath,
        };
      }

      if (!item.file) {
        throw new Error(`File content not found for ${item.fileName}`);
      }

      const controller = new AbortController();
      controllersRef.current.set(item.id, controller);
      patch(item.id, { phase: 'requesting-url', progress: 0, error: undefined });

      try {
        const target = await requestUploadUrl({
          fileName: item.fileName,
          contentType: item.file.type || 'application/pdf',
          size: item.file.size,
        });

        patch(item.id, { phase: 'uploading', progress: 0 });

        await uploadToPresignedUrl({
          uploadUrl: target.uploadUrl,
          file: item.file,
          signal: controller.signal,
          onProgress: (percent) => patch(item.id, { progress: percent }),
        });

        patch(item.id, {
          phase: 'ready',
          progress: 100,
          fileId: target.fileId,
          blobPath: target.blobPath,
        });

        return {
          fileId: target.fileId,
          fileName: item.fileName,
          size: item.size,
          blobPath: target.blobPath,
        };
      } catch (error) {
        if ((error as Error)?.name === 'AbortError') {
          patch(item.id, { phase: 'cancelled' });
        } else {
          patch(item.id, {
            phase: 'error',
            error: error instanceof Error ? error.message : 'Upload failed',
          });
        }
        throw error;
      } finally {
        controllersRef.current.delete(item.id);
      }
    },
    [patch],
  );

  const uploadPendingAttachments = useCallback(async (): Promise<MessageAttachment[]> => {
    const currentList = attachments;
    const results: MessageAttachment[] = [];

    for (const item of currentList) {
      if (item.phase === 'ready' && item.fileId) {
        results.push({
          fileId: item.fileId,
          fileName: item.fileName,
          size: item.size,
          blobPath: item.blobPath,
        });
        continue;
      }

      if (item.phase === 'selected' || item.phase === 'error') {
        const uploaded = await uploadSingle(item);
        results.push(uploaded);
      }
    }

    return results;
  }, [attachments, uploadSingle]);

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

  return {
    attachments,
    attachFile,
    uploadPendingAttachments,
    removeAttachment,
    clearAttachments,
  };
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
