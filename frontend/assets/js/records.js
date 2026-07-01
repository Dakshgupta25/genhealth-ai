class HealthRecordsManager {
  constructor() {
    this.records = [];
    this.currentPage = 1;
    this.perPage = 10;
    this.currentFilterType = null;
    this.includeFamily = false;
    this.searchQuery = '';
    this.total = 0;
  }

  async loadRecords(page = 1) {
    this.currentPage = page;
    this.renderSkeletons();

    try {
      const filters = {
        page: this.currentPage,
        per_page: this.perPage,
        record_type: this.currentFilterType,
        include_family: this.includeFamily
      };

      const res = await window.api.getRecords(filters);
      if (res.success && res.data) {
        this.records = res.data;
        this.total = res.meta ? res.meta.total : res.data.length;
        this.renderList();
      }
    } catch (err) {
      window.app.showToast(`❌ Error fetching records: ${err.message}`);
      this.renderEmptyState('Error loading records. Please retry.');
    }
  }

  renderSkeletons() {
    const list = document.getElementById('recordsList');
    if (!list) return;

    list.innerHTML = '';
    for (let i = 0; i < 4; i++) {
      const skeletonCard = document.createElement('div');
      skeletonCard.className = 'skeleton-card';
      skeletonCard.innerHTML = `
        <div style="display:flex; gap:16px; align-items:center;">
          <div class="skeleton skeleton-circle"></div>
          <div style="flex:1;">
            <div class="skeleton skeleton-text" style="width: 50%;"></div>
            <div class="skeleton skeleton-text" style="width: 30%;"></div>
          </div>
        </div>
        <div class="skeleton skeleton-text" style="width: 80%; margin-top:8px;"></div>
      `;
      list.appendChild(skeletonCard);
    }
  }

  renderList() {
    const list = document.getElementById('recordsList');
    if (!list) return;
    list.innerHTML = '';

    // Apply client-side search keyword filtering on title/entities if any query set
    let displayRecords = this.records;
    if (this.searchQuery) {
      const q = this.searchQuery.toLowerCase();
      displayRecords = this.records.filter(r => {
        const titleMatch = r.record_type.toLowerCase().includes(q) || (r.record_date && r.record_date.includes(q));
        const entityMatch = r.extracted_entities && r.extracted_entities.some(e => e.effective_value.toLowerCase().includes(q));
        return titleMatch || entityMatch;
      });
    }

    if (displayRecords.length === 0) {
      this.renderEmptyState();
      return;
    }

    displayRecords.forEach(rec => {
      const card = document.createElement('div');
      card.className = 'record-card';
      card.addEventListener('click', () => this.openRecordDetail(rec.id));

      let icon = '📄';
      let iconBg = '#F1F5F9';
      let iconColor = 'var(--color-muted)';

      if (rec.record_type.toLowerCase().includes('prescription')) {
        icon = '💊';
        iconBg = 'rgba(59, 130, 246, 0.1)';
        iconColor = '#3B82F6';
      } else if (rec.record_type.toLowerCase().includes('report') || rec.record_type.toLowerCase().includes('lab')) {
        icon = '🧪';
        iconBg = 'rgba(0, 196, 154, 0.1)';
        iconColor = 'var(--color-accent)';
      }

      const formattedDate = rec.record_date 
        ? new Date(rec.record_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
        : new Date(rec.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });

      // Build text tags for entities
      let tagsHtml = '';
      if (rec.extracted_entities && rec.extracted_entities.length > 0) {
        tagsHtml = rec.extracted_entities.slice(0, 3).map(e => {
          const type = e.entity_type.toLowerCase();
          let tagClass = 'badge-grey';
          if (type === 'disease' || type === 'condition') tagClass = 'badge-high';
          else if (type === 'medicine') tagClass = 'badge-blue';
          return `<span class="badge ${tagClass}" style="font-size: 9px; padding: 2px 6px;">${e.effective_value || e.entity_value}</span>`;
        }).join(' ');
      }

      const sourceLabel = rec.is_family_record ? '<span class="badge badge-purple" style="font-size:8px; margin-left:6px; padding:2px 4px;">Family Link</span>' : '';

      card.innerHTML = `
        <div class="record-icon" style="background: ${iconBg}; color: ${iconColor};">${icon}</div>
        <div class="record-content">
          <div class="record-title" style="display:flex; align-items:center;">
            ${rec.record_type.replace('_', ' ').toUpperCase()} ${sourceLabel}
          </div>
          <div class="record-meta">Uploaded: ${formattedDate} · Status: <strong>${rec.extraction_status.toUpperCase()}</strong></div>
          <div class="record-tags">${tagsHtml}</div>
        </div>
      `;
      list.appendChild(card);
    });
  }

  renderEmptyState(customMsg = null) {
    const list = document.getElementById('recordsList');
    if (!list) return;

    list.innerHTML = `
      <div style="text-align:center; padding: 48px 24px; color:var(--color-muted);">
        <div style="font-size: 48px; margin-bottom:16px;">📁</div>
        <div style="font-size: 16px; font-weight:600; color:var(--color-text); margin-bottom:8px;">
          ${customMsg || 'No health records found'}
        </div>
        <p style="font-size:13px; max-width: 260px; margin: 0 auto 20px;">
          ${this.searchQuery ? 'Try adjusting your search keywords.' : 'Upload a prescription or lab report to kick off AI extraction.'}
        </p>
        ${this.searchQuery ? '' : '<button class="btn btn-primary" onclick="window.location.hash=\'#upload\'">Upload Document</button>'}
      </div>
    `;
  }

  toggleFilter(el, type) {
    // Toggle active class on filter chips
    document.querySelectorAll('#filterChips .chip').forEach(c => c.classList.remove('active'));
    el.classList.add('active');

    this.currentFilterType = type === 'all' ? null : type;
    this.loadRecords(1);
  }

  toggleFamilyRecords(checkbox) {
    this.includeFamily = checkbox.checked;
    this.loadRecords(1);
  }

  handleSearch(query) {
    this.searchQuery = query;
    this.renderList(); // apply instant filter on already loaded page array
  }

  async openRecordDetail(recordId) {
    try {
      window.app.showLoader(true);
      const res = await window.api.getRecord(recordId);
      if (res.success && res.data) {
        const rec = res.data;
        document.getElementById('detailTitle').textContent = rec.record_type.replace('_', ' ').toUpperCase();
        
        const content = document.getElementById('detailContent');
        const formattedDate = rec.record_date 
          ? new Date(rec.record_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })
          : 'Extraction failed/pending';

        // Map all entities to details view
        let entitiesHtml = '';
        if (rec.extracted_entities && rec.extracted_entities.length > 0) {
          entitiesHtml = rec.extracted_entities.map(e => `
            <div style="padding: 10px; background:var(--color-bg); border-radius:8px; margin-bottom:8px; border: 1px solid var(--color-border);">
              <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--color-muted); text-transform:uppercase;">
                <span>${e.entity_type}</span>
                <span>Confidence: ${(e.confidence * 100).toFixed(0)}%</span>
              </div>
              <div style="font-size:14px; font-weight:500; color:var(--color-text); margin-top:4px;">${e.effective_value || e.entity_value}</div>
              ${e.icd10_code ? `<div style="font-size:11px; color:var(--color-muted); margin-top:2px;">ICD-10: <strong>${e.icd10_code}</strong></div>` : ''}
              ${e.atc_code ? `<div style="font-size:11px; color:var(--color-muted); margin-top:2px;">ATC Code: <strong>${e.atc_code}</strong></div>` : ''}
            </div>
          `).join('');
        } else {
          entitiesHtml = '<div style="font-size:13px; color:var(--color-muted);">No structured entities available.</div>';
        }

        content.innerHTML = `
          <div class="detail-field">
            <div class="detail-field-label">Document Date</div>
            <div class="detail-field-value">${formattedDate}</div>
          </div>
          <div class="detail-field">
            <div class="detail-field-label">Verification Status</div>
            <div class="detail-field-value">${rec.is_verified_by_user ? '✅ User Verified' : '⏳ Pending User Verification'}</div>
          </div>
          <div class="detail-field">
            <div class="detail-field-label">Document URL</div>
            <div class="detail-field-value">
              <a href="${rec.source_file_url}" target="_blank" style="color:var(--color-accent); text-decoration:underline;">View original file</a>
            </div>
          </div>
          <div class="detail-field" style="margin-top:20px;">
            <div class="detail-field-label" style="margin-bottom:10px;">AI SURFACED DATA</div>
            ${entitiesHtml}
          </div>
          <div style="margin-top: 24px; display:flex; gap:10px; flex-direction: column;">
            <div style="display:flex; gap:10px;">
              <button class="btn btn-primary" style="flex:1;" onclick="records.downloadStub()">Download PDF</button>
              <button class="btn btn-outline" style="flex:1;" onclick="records.shareStub()">Share Link</button>
            </div>
            <button class="btn btn-danger" style="width:100%;" onclick="records.deleteRecord('${rec.id}')">Delete Record</button>
          </div>
        `;

        document.getElementById('detailOverlay').classList.add('active');
      }
    } catch (e) {
      window.app.showToast(`❌ Detail loading failed: ${e.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }

  async deleteRecord(recordId) {
    if (!confirm('Are you sure you want to delete this health record? This will permanently remove the record and recalculate your health risk predictions.')) {
      return;
    }
    try {
      window.app.showLoader(true);
      const res = await window.api.request('DELETE', `/records/${recordId}`);
      if (res.success) {
        window.app.showToast('✓ Record deleted successfully.');
        document.getElementById('detailOverlay').classList.remove('active');
        // Regenerate prediction models since a record has been deleted
        try {
          await window.api.generateRisk();
        } catch (e) {
          console.warn('Risk auto-generation failed', e);
        }
        await this.loadRecords(this.currentPage);
      }
    } catch (e) {
      window.app.showToast(`❌ Deletion failed: ${e.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }

  downloadStub() {
    window.app.showToast('📥 Downloading medical record PDF...');
  }

  shareStub() {
    window.app.showToast('📋 Share link copied to clipboard!');
  }
}

const records = new HealthRecordsManager();
window.records = records;
