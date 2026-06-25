class RecommendationsManager {
  constructor() {
    this.recs = [];
    this.currentCategory = null;
  }

  async loadRecommendations() {
    try {
      window.app.showLoader(true);
      const res = await window.api.getRecommendations(this.currentCategory);
      if (res.success && res.data) {
        this.recs = res.data.recommendations || [];
        this.renderList();
      }
    } catch (e) {
      window.app.showToast(`❌ Error loading recommendations: ${e.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }

  renderList() {
    const container = document.getElementById('recommendationsList');
    if (!container) return;
    container.innerHTML = '';

    if (this.recs.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding: 48px 24px; color:var(--color-muted);">
          <div style="font-size: 48px; margin-bottom:16px;">🌱</div>
          <div style="font-size: 16px; font-weight:600; color:var(--color-text); margin-bottom:8px;">No recommendations yet</div>
          <p style="font-size:13px; max-width: 280px; margin: 0 auto;">
            GenHealth AI generates personalized suggestions once health records or risk profiles are updated.
          </p>
        </div>
      `;
      return;
    }

    this.recs.forEach(rec => {
      const card = document.createElement('div');
      card.className = 'rec-full-card';

      let icon = '💡';
      let iconBg = 'rgba(0, 196, 154, 0.1)';

      const cat = rec.category.toLowerCase();
      if (cat === 'diet') {
        icon = '🍚';
        iconBg = 'rgba(239, 68, 68, 0.1)';
      } else if (cat === 'exercise') {
        icon = '🚶‍♂️';
        iconBg = 'rgba(59, 130, 246, 0.1)';
      } else if (cat === 'sleep') {
        icon = '🌙';
        iconBg = 'rgba(139, 92, 246, 0.1)';
      } else if (cat === 'checkup') {
        icon = '🩺';
        iconBg = 'rgba(245, 158, 11, 0.1)';
      }

      const priorityClass = rec.priority === 'urgent' ? 'badge-high' : 'badge-accent';

      card.innerHTML = `
        <div class="rec-full-icon" style="background: ${iconBg};">${icon}</div>
        <div class="rec-full-content">
          <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom:6px;">
            <div class="rec-full-title">${rec.title}</div>
            <span class="badge ${priorityClass}" style="font-size:10px;">${rec.priority}</span>
          </div>
          <div class="rec-full-meta">${rec.category_label || rec.category} · ${rec.reason || 'General health guidance'}</div>
          <div style="font-size:13px; color:var(--color-muted); margin-bottom:12px; line-height:1.5;">${rec.description}</div>
          <div class="rec-reminder-row">
            <span>Set reminder</span>
            <label class="toggle">
              <input type="checkbox" onchange="recommendations.toggleReminder(this, '${rec.title}')">
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>
      `;

      container.appendChild(card);
    });
  }

  async toggleReminder(checkbox, title) {
    const isSet = checkbox.checked;
    if (isSet) {
      try {
        const res = await window.api.request('POST', `/recommendations/remind?title=${encodeURIComponent(title)}`);
        if (res.success) {
          window.app.showToast('🔔 Reminder set successfully!');
        }
      } catch (err) {
        window.app.showToast('❌ Could not schedule reminder.');
        checkbox.checked = false;
      }
    } else {
      window.app.showToast('Reminder removed.');
    }
  }

  filterCategory(el, category) {
    document.querySelectorAll('#recTabs .tab-item').forEach(btn => btn.classList.remove('active'));
    el.classList.add('active');

    this.currentCategory = category === 'all' ? null : category;
    this.loadRecommendations();
  }
}

const recommendations = new RecommendationsManager();
window.recommendations = recommendations;
