/**
 * GenHealth AI — Upload Module
 *
 * Handles:
 * - Drag-and-drop file selection
 * - File validation (type + size)
 * - Multipart upload to the backend
 * - Real-time progress simulation
 * - Polling for Celery task completion
 */

const Upload = (() => {
  const { upload, ApiError } = window.GenHealthAPI;

  const MAX_SIZE_MB = 20;
  const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/heic", "application/pdf"];
  const ALLOWED_EXTS = [".jpg", ".jpeg", ".png", ".heic", ".pdf"];

  // ─── Validation ───────────────────────────────────────────────────────────

  /**
   * Validate a File object for type and size.
   * @param {File} file
   * @returns {{ valid: boolean, error?: string }}
   */
  function validateFile(file) {
    const ext = "." + file.name.split(".").pop().toLowerCase();
    const isTypeOk = ALLOWED_TYPES.includes(file.type) || ALLOWED_EXTS.includes(ext);
    if (!isTypeOk) {
      return {
        valid: false,
        error: `File type '${ext}' is not supported. Please upload a JPG, PNG, PDF, or HEIC.`,
      };
    }
    const sizeMB = file.size / 1024 / 1024;
    if (sizeMB > MAX_SIZE_MB) {
      return {
        valid: false,
        error: `File is too large (${sizeMB.toFixed(1)}MB). Maximum size is ${MAX_SIZE_MB}MB.`,
      };
    }
    return { valid: true };
  }

  // ─── Upload ───────────────────────────────────────────────────────────────

  /**
   * Upload a file to the backend and return the created record.
   *
   * @param {File}   file            - The file to upload
   * @param {string} recordType      - 'prescription' | 'lab_report' | ...
   * @param {string} familyMemberId  - Optional UUID of a family member
   * @param {Function} onProgress    - (pct: number) => void progress callback
   * @returns {Promise<object>}      - The created HealthRecord
   */
  async function uploadFile(file, recordType = "prescription", familyMemberId = null, onProgress = null) {
    const validation = validateFile(file);
    if (!validation.valid) throw new Error(validation.error);

    if (onProgress) onProgress(10);

    const result = await upload.uploadFile(file, recordType, familyMemberId);

    if (onProgress) onProgress(60);

    return result;
  }

  // ─── Task Polling ─────────────────────────────────────────────────────────

  /**
   * Poll a Celery task until it completes or fails.
   *
   * @param {string}   taskId      - The Celery task ID
   * @param {Function} onUpdate    - ({state, info}) => void callback
   * @param {number}   intervalMs  - Poll interval in ms (default 2000)
   * @param {number}   maxAttempts - Max poll attempts (default 30)
   * @returns {Promise<string>}    - Final task state
   */
  async function pollTaskStatus(taskId, onUpdate = null, intervalMs = 2000, maxAttempts = 30) {
    return new Promise((resolve, reject) => {
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        try {
          const data = await upload.taskStatus(taskId);
          if (onUpdate) onUpdate(data);

          if (data.state === "SUCCESS") {
            clearInterval(interval);
            resolve("SUCCESS");
          } else if (data.state === "FAILURE") {
            clearInterval(interval);
            reject(new Error("OCR processing failed."));
          } else if (attempts >= maxAttempts) {
            clearInterval(interval);
            resolve("TIMEOUT");
          }
        } catch (e) {
          clearInterval(interval);
          reject(e);
        }
      }, intervalMs);
    });
  }

  // ─── Drag-and-drop setup ─────────────────────────────────────────────────

  /**
   * Set up drag-and-drop on a dropzone element.
   *
   * @param {HTMLElement} dropzone   - The drop target element
   * @param {HTMLElement} fileInput  - The <input type="file"> element
   * @param {Function}    onFile     - (file: File) => void callback
   */
  function setupDropzone(dropzone, fileInput, onFile) {
    if (!dropzone) return;

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("drag-over");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("drag-over");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
      const file = e.dataTransfer?.files?.[0];
      if (file) onFile(file);
    });

    if (fileInput) {
      fileInput.addEventListener("change", () => {
        const file = fileInput.files?.[0];
        if (file) onFile(file);
      });
    }

    dropzone.addEventListener("click", () => fileInput?.click());
  }

  return { validateFile, uploadFile, pollTaskStatus, setupDropzone };
})();

window.Upload = Upload;
