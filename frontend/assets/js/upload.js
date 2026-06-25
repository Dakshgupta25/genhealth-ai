class PrescriptionUploader {
  constructor() {
    this.file = null;
    this.pollInterval = null;
    this.recordId = null;
    this.taskId = null;
    this.entities = [];
  }

  init() {
    const zone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const selectBtn = document.getElementById('selectFileBtn');
    const cameraBtn = document.getElementById('cameraBtn');
    const uploadBtn = document.getElementById('startUploadBtn');

    if (!zone) return;

    // Drag and drop handlers
    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.classList.add('drag-over');
    });

    zone.addEventListener('dragleave', () => {
      zone.classList.remove('drag-over');
    });

    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      if (e.dataTransfer.files.length > 0) {
        this.handleFile(e.dataTransfer.files[0]);
      }
    });

    // File input handlers
    if (selectBtn && fileInput) {
      selectBtn.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
          this.handleFile(e.target.files[0]);
        }
      });
    }

    // Mobile camera handler
    if (cameraBtn && fileInput) {
      cameraBtn.addEventListener('click', () => {
        fileInput.setAttribute('capture', 'environment');
        fileInput.setAttribute('accept', 'image/*');
        fileInput.click();
      });
    }

    // Start upload trigger
    if (uploadBtn) {
      uploadBtn.addEventListener('click', () => this.upload());
    }
  }

  handleFile(file) {
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    const maxSizeBytes = 20 * 1024 * 1024; // 20MB

    if (!allowedTypes.includes(file.type)) {
      window.app.showToast('❌ Unsupported file type. Please upload JPEG, PNG, WEBP or PDF.');
      return;
    }

    if (file.size > maxSizeBytes) {
      window.app.showToast('❌ File is too large. Maximum size allowed is 20MB.');
      return;
    }

    this.file = file;

    // Render preview thumbnail
    const previewContainer = document.getElementById('uploadPreview');
    const previewImg = document.getElementById('previewThumbnail');
    const fileNameText = document.getElementById('previewFileName');
    const dropzoneContent = document.getElementById('dropzoneContent');
    const uploadBtn = document.getElementById('startUploadBtn');

    if (fileNameText) fileNameText.textContent = `${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;

    if (file.type.startsWith('image/') && previewImg) {
      const reader = new FileReader();
      reader.onload = (e) => {
        previewImg.src = e.target.result;
        previewImg.style.display = 'block';
      };
      reader.readAsDataURL(file);
    } else if (previewImg) {
      // PDF placeholder thumbnail
      previewImg.style.display = 'none';
    }

    if (dropzoneContent) dropzoneContent.style.display = 'none';
    if (previewContainer) previewContainer.style.display = 'block';
    if (uploadBtn) uploadBtn.removeAttribute('disabled');
  }

  async upload() {
    if (!this.file) return;

    const recordType = document.getElementById('uploadRecordType')?.value || 'prescription';
    const familyMemberId = document.getElementById('uploadFamilyMember')?.value || null;

    const zone = document.getElementById('uploadPreview');
    const proc = document.getElementById('processingState');
    const startUploadBtn = document.getElementById('startUploadBtn');

    if (zone) zone.style.display = 'none';
    if (startUploadBtn) startUploadBtn.style.display = 'none';
    if (proc) proc.classList.add('active');

    this.updateProgressStep(1, 'Uploading file...');

    try {
      const res = await window.api.uploadPrescription(this.file, recordType, familyMemberId);
      
      if (res.success && res.data) {
        this.recordId = res.data.record.id;
        this.taskId = res.data.task_id;

        if (this.taskId) {
          // Poll Celery status
          this.pollStatus(this.taskId);
        } else {
          // Fallback: poll record status directly
          this.pollRecordStatus(this.recordId);
        }
      }
    } catch (err) {
      window.app.showToast(`❌ Upload failed: ${err.message}`);
      this.reset();
    }
  }

  updateProgressStep(step, message) {
    const stepNum = document.getElementById('procStepNum');
    const stepMsg = document.getElementById('procStepMsg');
    const progressBar = document.getElementById('uploadProgressBar');

    if (stepNum) stepNum.textContent = `Step ${step} of 5`;
    if (stepMsg) stepMsg.textContent = message;
    if (progressBar) {
      const w = step * 20;
      progressBar.style.width = `${w}%`;
    }
  }

  pollStatus(taskId) {
    let checkCount = 0;
    this.pollInterval = setInterval(async () => {
      checkCount++;
      try {
        const res = await window.api.request('GET', `/upload/status/${taskId}`);
        if (res.success && res.data) {
          const state = res.data.state;

          if (state === 'PENDING') {
            this.updateProgressStep(1, 'Uploading file...');
          } else if (state === 'STARTED' || state === 'PROGRESS') {
            // Update steps based on simulation or task meta info
            const step = Math.min(2 + Math.floor(checkCount / 3), 4);
            const messages = {
              2: 'Running OCR text extraction...',
              3: 'Extracting medical entities with AI NLP...',
              4: 'Mapping diseases and medicines to standard codes...'
            };
            this.updateProgressStep(step, messages[step]);
          } else if (state === 'SUCCESS') {
            this.updateProgressStep(5, 'AI processing complete!');
            clearInterval(this.pollInterval);
            
            // Wait brief moment and fetch extracted entities
            setTimeout(() => this.fetchExtractedDetails(), 600);
          } else if (state === 'FAILURE') {
            clearInterval(this.pollInterval);
            window.app.showToast('❌ AI OCR Pipeline failed. Please check the document.');
            this.reset();
          }
        }
      } catch (err) {
        console.error('Error polling Celery task status:', err);
      }
    }, 2000);
  }

  // Fallback direct polling if Celery task is not stored
  pollRecordStatus(recordId) {
    this.pollInterval = setInterval(async () => {
      try {
        const res = await window.api.getRecord(recordId);
        if (res.success && res.data) {
          const status = res.data.extraction_status;
          
          if (status === 'pending') {
            this.updateProgressStep(2, 'Running OCR & AI extraction...');
          } else if (status === 'done') {
            this.updateProgressStep(5, 'AI processing complete!');
            clearInterval(this.pollInterval);
            this.renderEntities(res.data);
          } else if (status === 'failed') {
            clearInterval(this.pollInterval);
            window.app.showToast('❌ Extraction failed.');
            this.reset();
          }
        }
      } catch (err) {
        console.error('Error polling record:', err);
      }
    }, 2000);
  }

  async fetchExtractedDetails() {
    try {
      const res = await window.api.getRecord(this.recordId);
      if (res.success && res.data) {
        this.renderEntities(res.data);
      }
    } catch (e) {
      window.app.showToast(`❌ Failed to retrieve extraction details: ${e.message}`);
      this.reset();
    }
  }

  renderEntities(record) {
    const proc = document.getElementById('processingState');
    const result = document.getElementById('extractionResult');
    const chipsContainer = document.getElementById('extractionChips');
    const confidenceText = document.getElementById('confidenceText');

    if (proc) proc.classList.remove('active');
    if (result) result.classList.add('active');

    const pct = record.confidence_pct || (record.confidence_score ? (record.confidence_score * 100).toFixed(0) : 90);
    if (confidenceText) confidenceText.textContent = `${pct}% Accuracy`;

    this.entities = record.extracted_entities || [];

    if (chipsContainer) {
      chipsContainer.innerHTML = '';
      if (this.entities.length === 0) {
        chipsContainer.innerHTML = '<span style="font-size:13px; color:var(--color-muted);">No medical entities surfaced.</span>';
      }

      this.entities.forEach(entity => {
        const chip = document.createElement('div');
        let chipClass = 'ext-chip-grey';
        let chipIcon = '🏷️';
        
        const type = entity.entity_type.toLowerCase();
        if (type === 'disease' || type === 'condition' || type === 'diagnoses') {
          chipClass = 'ext-chip-red';
          chipIcon = '🩸';
        } else if (type === 'medicine' || type === 'medication' || type === 'drug') {
          chipClass = 'ext-chip-blue';
          chipIcon = '💊';
        } else if (type === 'doctor' || type === 'provider') {
          chipClass = 'ext-chip-purple';
          chipIcon = '👨‍⚕️';
        } else if (type === 'date') {
          chipClass = 'ext-chip-grey';
          chipIcon = '📅';
        }

        chip.className = `ext-chip ${chipClass}`;
        
        // Editable template using contenteditable
        chip.innerHTML = `
          <span>${chipIcon}</span>
          <strong style="margin-right:4px;">${entity.entity_type}:</strong>
          <span class="entity-val" contenteditable="true" data-id="${entity.id}" style="outline:none; border-bottom: 1px dashed rgba(0,0,0,0.3); min-width: 40px; display: inline-block;">${entity.effective_value || entity.entity_value}</span>
          <span style="font-size:10px; opacity:0.65; margin-left: 6px;">(${((entity.confidence || 0.9) * 100).toFixed(0)}%)</span>
        `;

        chipsContainer.appendChild(chip);
      });
    }
  }

  async saveVerification() {
    const valueSpans = document.querySelectorAll('#extractionChips .entity-val');
    const corrections = [];

    valueSpans.forEach(span => {
      const id = span.dataset.id;
      const original = this.entities.find(e => e.id === id);
      const val = span.textContent.trim();

      if (original && (original.effective_value !== val || original.entity_value !== val)) {
        corrections.push({
          entity_id: id,
          corrected_value: val
        });
      }
    });

    try {
      window.app.showLoader(true);
      const res = await window.api.verifyRecord(this.recordId, corrections);
      if (res.success) {
        window.app.showToast('✓ Record verified and saved to profile!');
        
        // Regenerate prediction models as we have a verified new record
        try {
          await window.api.generateRisk();
        } catch (e) {
          console.warn('Risk auto-generation failed', e);
        }

        this.reset();
        setTimeout(() => {
          window.location.hash = '#records';
        }, 1200);
      }
    } catch (e) {
      window.app.showToast(`❌ Save failed: ${e.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }

  reset() {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.file = null;
    this.recordId = null;
    this.taskId = null;
    this.entities = [];

    const zone = document.getElementById('uploadZone');
    const preview = document.getElementById('uploadPreview');
    const proc = document.getElementById('processingState');
    const result = document.getElementById('extractionResult');
    const startUploadBtn = document.getElementById('startUploadBtn');
    const fileInput = document.getElementById('fileInput');

    if (fileInput) fileInput.value = '';
    if (zone) zone.style.display = 'block';
    if (preview) preview.style.display = 'none';
    if (proc) proc.classList.remove('active');
    if (result) result.classList.remove('active');
    if (startUploadBtn) {
      startUploadBtn.style.display = 'inline-flex';
      startUploadBtn.setAttribute('disabled', 'true');
    }
  }
}

const uploader = new PrescriptionUploader();
window.uploader = uploader;
