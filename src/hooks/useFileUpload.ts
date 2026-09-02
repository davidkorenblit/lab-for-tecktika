import { useCallback, useRef, useState } from 'react';
import { uid } from '@/lib/format';
import { uploadToPresignedUrl } from '@/services/blobUpload';
import { confirmAction, finalizeUpload, requestUploadUrl } from '@/services/files';
import { useJobs } from '@/providers/JobsProvider';
import { describeJob } from './useChat';
import type { ConfirmationRequest, UploadTask, UploadUrlResponse } from '@/types';

/**
 * Two-step upload for large PDFs.
 *
 *   1. POST /api/files/upload-url  -> short-lived SAS URL (no bytes through the API)
 *   2. PUT straight to storage     -> single shot, or staged blocks for 50 MB+
 *   3. POST /api/files/confirm-action -> backend indexes the file, returns a jobId
 *
 * If step 1 reports that the name is already taken, the upload parks in
 * `awaiting-confirmation` and nothing is sent until the user approves the
 * overwrite in a dialog that names the file.
 */
export function useFileUpload() {
  const { trackJob } = useJobs();
  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const controllersRef = useRef<Map<string, AbortController>>(new Map());
  const pendingFilesRef = useRef<Map<string, File>>(new Map());

  const patchTask = useCallback((taskId: string, patch: Partial<UploadTask>) => {
    setTasks((current) => current.map((task) => (task.id === taskId ? { ...task, ...patch } : task)));
  }, []);

  const runUpload = useCallback(
    async (taskId: string, file: File, urlResponse: UploadUrlResponse) => {
      const controller = new AbortController();
      controllersRef.current.set(taskId, controller);

      try {
        patchTask(taskId, { phase: 'uploading', progress: 0, error: undefined });

        await uploadToPresignedUrl({
          uploadUrl: urlResponse.uploadUrl,
          file,
          signal: controller.signal,
          onProgress: (percent) => patchTask(taskId, { progress: percent }),
        });

        patchTask(taskId, { phase: 'finalizing', progress: 100 });

        const result = await finalizeUpload({
          fileId: urlResponse.fileId,
          fileName: file.name,
          blobPath: urlResponse.blobPath,
          confirmationId: urlResponse.requiresConfirmation?.confirmationId,
        });

        if (result.jobId) {
          // Indexing continues server-side; the tracked job is what the user
          // follows from here, and it survives a refresh.
          trackJob({
            jobId: result.jobId,
            action: 'upload',
            label: describeJob('upload', file.name),
            fileName: file.name,
          });
        }

        patchTask(taskId, { phase: 'done', jobId: result.jobId });
      } catch (error) {
        if ((error as Error)?.name === 'AbortError') {
          patchTask(taskId, { phase: 'cancelled' });
        } else {
          patchTask(taskId, {
            phase: 'error',
            error: error instanceof Error ? error.message : 'Upload failed',
          });
        }
      } finally {
        controllersRef.current.delete(taskId);
        pendingFilesRef.current.delete(taskId);
      }
    },
    [patchTask, trackJob],
  );

  const startUpload = useCallback(
    async (file: File) => {
      const taskId = uid('upload');
      setTasks((current) => [
        ...current,
        { id: taskId, fileName: file.name, size: file.size, phase: 'requesting-url', progress: 0 },
      ]);
      pendingFilesRef.current.set(taskId, file);

      try {
        const urlResponse = await requestUploadUrl({
          fileName: file.name,
          contentType: file.type || 'application/pdf',
          size: file.size,
        });

        if (urlResponse.requiresConfirmation && !urlResponse.uploadUrl) {
          // Overwrite detected — stop and ask, naming the file.
          patchTask(taskId, {
            phase: 'awaiting-confirmation',
            confirmation: urlResponse.requiresConfirmation,
          });
          return taskId;
        }

        await runUpload(taskId, file, urlResponse);
      } catch (error) {
        patchTask(taskId, {
          phase: 'error',
          error: error instanceof Error ? error.message : 'Could not start the upload',
        });
      }

      return taskId;
    },
    [patchTask, runUpload],
  );

  /** Called from the confirmation dialog once the user approves an overwrite. */
  const confirmOverwrite = useCallback(
    async (taskId: string, confirmation: ConfirmationRequest) => {
      const file = pendingFilesRef.current.get(taskId);
      if (!file) {
        patchTask(taskId, { phase: 'error', error: 'The selected file is no longer available' });
        return;
      }

      try {
        patchTask(taskId, { phase: 'requesting-url', confirmation: undefined });

        await confirmAction({
          confirmationId: confirmation.confirmationId,
          confirmed: true,
          action: confirmation.action,
          files: confirmation.files.map((entry) => entry.name),
        });

        const urlResponse = await requestUploadUrl({
          fileName: file.name,
          contentType: file.type || 'application/pdf',
          size: file.size,
          overwrite: true,
        });

        await runUpload(taskId, file, urlResponse);
      } catch (error) {
        patchTask(taskId, {
          phase: 'error',
          error: error instanceof Error ? error.message : 'Could not confirm the overwrite',
        });
      }
    },
    [patchTask, runUpload],
  );

  const declineOverwrite = useCallback(
    async (taskId: string, confirmation: ConfirmationRequest) => {
      patchTask(taskId, { phase: 'cancelled', confirmation: undefined });
      pendingFilesRef.current.delete(taskId);
      await confirmAction({
        confirmationId: confirmation.confirmationId,
        confirmed: false,
        action: confirmation.action,
        files: confirmation.files.map((entry) => entry.name),
      }).catch(() => undefined);
    },
    [patchTask],
  );

  const cancelUpload = useCallback((taskId: string) => {
    controllersRef.current.get(taskId)?.abort();
  }, []);

  const dismissTask = useCallback((taskId: string) => {
    controllersRef.current.get(taskId)?.abort();
    controllersRef.current.delete(taskId);
    pendingFilesRef.current.delete(taskId);
    setTasks((current) => current.filter((task) => task.id !== taskId));
  }, []);

  return { tasks, startUpload, cancelUpload, dismissTask, confirmOverwrite, declineOverwrite };
}
