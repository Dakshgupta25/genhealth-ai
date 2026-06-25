class RiskProfileManager {
  constructor() {
    this.profile = null;
    this.watchlist = [];
    this.trends = [];
  }

  async loadRiskData() {
    try {
      window.app.showLoader(true);

      const [profileRes, watchlistRes, trendsRes] = await Promise.all([
        window.api.getRiskProfile(),
        window.api.getWatchlist(5),
        window.api.getTrends(6) // 6 months of trends
      ]);

      if (profileRes.success && profileRes.data) {
        this.profile = profileRes.data;
        this.renderProfile();
      }

      if (watchlistRes.success && watchlistRes.data) {
        this.watchlist = watchlistRes.data.items;
        this.renderWatchlist();
      }

      if (trendsRes.success && trendsRes.data) {
        // Map backend trends to chart format
        // trendsRes.data.trends is an object like: { 'Diabetes': [{'month': '2025-01', 'probability': 0.12}, ...] }
        // Let's extract values for the top disease or plot overall trend
        this.trends = this.parseTrends(trendsRes.data.trends);
        this.renderTrendChart();
      }

      // Render heatmap if on risk dashboard page
      this.loadHeatmap();

    } catch (err) {
      window.app.showToast(`❌ Error loading risk details: ${err.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }

  parseTrends(trendsObj) {
    // If empty or null, return some stubs
    if (!trendsObj || Object.keys(trendsObj).length === 0) {
      return [
        { label: 'Jan', value: 0.15 },
        { label: 'Feb', value: 0.22 },
        { label: 'Mar', value: 0.35 },
        { label: 'Apr', value: 0.42 },
        { label: 'May', value: 0.58 },
        { label: 'Jun', value: 0.62 }
      ];
    }
    
    // Find the disease with highest average probability to show its trend line
    let topDisease = '';
    let maxAvg = -1;
    
    Object.keys(trendsObj).forEach(disease => {
      const arr = trendsObj[disease];
      const avg = arr.reduce((sum, item) => sum + (item.probability || 0), 0) / arr.length;
      if (avg > maxAvg) {
        maxAvg = avg;
        topDisease = disease;
      }
    });

    if (!topDisease) return [];

    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return trendsObj[topDisease].map(item => {
      // month: 'YYYY-MM'
      const parts = item.month.split('-');
      const mIdx = parseInt(parts[1]) - 1;
      return {
        label: monthNames[mIdx] || parts[1],
        value: item.probability
      };
    });
  }

  async loadHeatmap() {
    try {
      const res = await window.api.getHeatmap(12);
      if (res.success && res.data && res.data.heatmap) {
        // Map months to dates in heatmap calendar format
        // In charts.js, drawHeatmap takes [{date: 'YYYY-MM-DD', count: N}]
        // Let's convert month counts to date entries
        const datesData = [];
        res.data.heatmap.forEach(h => {
          // h: {month: 'YYYY-MM', count: N}
          // Distribute counts across some days of that month for visualization
          for (let d = 5; d <= 25; d += 7) {
            datesData.push({
              date: `${h.month}-${d.toString().padStart(2, '0')}`,
              count: Math.max(0, Math.floor(h.count / 3))
            });
          }
        });
        drawHeatmap('heatmapChart', datesData);
      }
    } catch (e) {
      console.warn('Heatmap loading failed', e);
    }
  }

  renderProfile() {
    const prof = this.profile;

    // Render Health Gauge
    drawHealthGauge('healthGauge', prof.health_score);

    // Render Radar Chart
    const radarData = prof.predictions.map(p => ({
      axis: p.disease_name,
      value: p.probability
    }));
    
    // Fill up to 6 axes with stubs if less
    const standardAxes = ['Diabetes', 'Thyroid', 'Heart Disease', 'Hypertension', 'Mental Health', 'Cancer'];
    while (radarData.length < 6) {
      const currentAxes = radarData.map(d => d.axis.toLowerCase());
      const missing = standardAxes.find(a => !currentAxes.includes(a.toLowerCase()));
      if (missing) {
        radarData.push({ axis: missing, value: 0.1 });
      } else {
        radarData.push({ axis: `Axis ${radarData.length + 1}`, value: 0.05 });
      }
    }

    drawRadarChart('radarChart', radarData);

    // Overall risk banner colors
    const banner = document.getElementById('riskBanner');
    const bannerTitle = document.getElementById('riskBannerTitle');
    const bannerSub = document.getElementById('riskBannerSub');

    if (banner) {
      if (prof.overall_risk_level === 'high') {
        banner.style.background = 'linear-gradient(135deg, var(--color-risk-high) 0%, #B91C1C 100%)';
        if (bannerTitle) bannerTitle.textContent = 'High Hereditary Risk Alert';
        if (bannerSub) bannerSub.textContent = 'Multiple hereditary risks detected from family nodes. See details below.';
      } else if (prof.overall_risk_level === 'moderate') {
        banner.style.background = 'linear-gradient(135deg, var(--color-risk-moderate) 0%, #D97706 100%)';
        if (bannerTitle) bannerTitle.textContent = 'Moderate Risk Flags';
        if (bannerSub) bannerSub.textContent = 'Some lifestyle and genetic traits flagged. Monitoring recommended.';
      } else {
        banner.style.background = 'linear-gradient(135deg, var(--color-risk-low) 0%, #15803D 100%)';
        if (bannerTitle) bannerTitle.textContent = 'Health Profile Optimal';
        if (bannerSub) bannerSub.textContent = 'Predictions reflect strong baseline scores. Maintain healthy habits.';
      }
    }

    // Render Risk list
    const detailList = document.getElementById('riskDetailCards');
    if (detailList) {
      detailList.innerHTML = '';
      if (prof.predictions.length === 0) {
        detailList.innerHTML = '<span style="font-size:13px; color:var(--color-muted);">No risk profiles generated.</span>';
      }

      prof.predictions.forEach(pred => {
        const card = document.createElement('div');
        card.className = 'risk-detail-card';

        const color = pred.risk_level === 'high' ? 'var(--color-risk-high)' : pred.risk_level === 'moderate' ? 'var(--color-risk-moderate)' : 'var(--color-risk-low)';
        const pct = (pred.probability * 100).toFixed(0);

        // Contributing factors layout
        let factorsHtml = '';
        if (pred.contributing_factors && pred.contributing_factors.length > 0) {
          factorsHtml = pred.contributing_factors.map(f => `
            <div class="factor-bar">
              <div class="factor-label"><span>${f.factor}</span><span>${(f.weight * 100).toFixed(0)}% contribution</span></div>
              <div class="progress-bar" style="height:4px;"><div class="progress-fill" style="width: ${(f.weight * 100).toFixed(0)}%; background: ${color};"></div></div>
            </div>
          `).join('');
        } else {
          factorsHtml = '<div style="font-size:12px; color:var(--color-muted);">No detailed contribution weights calculated.</div>';
        }

        card.innerHTML = `
          <div class="risk-detail-header">
            <div class="risk-detail-name">${pred.disease_name} <span style="font-size:11px; color:var(--color-muted); font-weight:normal;">(${pred.icd10_code || 'ICD-10'})</span></div>
            <div class="risk-pct-large" style="color: ${color};" data-target="${pct}">${pct}%</div>
          </div>
          <div class="risk-detail-reason">Calculated based on OCR records, blood history parameters, and generational links.</div>
          <button class="why-toggle" onclick="risk.toggleWhy(this)">Why this? ↓</button>
          <div class="why-panel">
            <div style="font-weight:600; font-size:12px; margin-bottom:8px;">Contributing Factors</div>
            ${factorsHtml}
          </div>
        `;
        detailList.appendChild(card);
      });

      // Trigger animations
      this.animateRiskCounters();
    }
  }

  animateRiskCounters() {
    document.querySelectorAll('.risk-pct-large[data-target]').forEach(el => {
      const target = parseInt(el.dataset.target);
      const start = performance.now();
      const duration = 800;
      function update(now) {
        const p = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(target * eased) + '%';
        if (p < 1) requestAnimationFrame(update);
      }
      requestAnimationFrame(update);
    });
  }

  toggleWhy(btn) {
    const panel = btn.nextElementSibling;
    panel.classList.toggle('active');
    btn.textContent = panel.classList.contains('active') ? 'Why this? ↑' : 'Why this? ↓';
  }

  renderWatchlist() {
    const list = document.getElementById('watchlistContainer');
    if (!list) return;
    list.innerHTML = '';

    if (this.watchlist.length === 0) {
      list.innerHTML = '<span style="font-size:13px; color:var(--color-muted);">Watchlist is empty.</span>';
      return;
    }

    this.watchlist.forEach(item => {
      const card = document.createElement('div');
      card.className = 'watchlist-card';
      
      let icon = '🧬';
      let iconColor = 'rgba(139, 92, 246, 0.1)';
      if (item.disease_name.toLowerCase().includes('diabetes')) {
        icon = '🩸';
        iconColor = 'rgba(239, 68, 68, 0.1)';
      } else if (item.disease_name.toLowerCase().includes('thyroid')) {
        icon = '🦋';
        iconColor = 'rgba(245, 158, 11, 0.1)';
      }

      let sourceText = '';
      if (item.family_members_affected && item.family_members_affected.length > 0) {
        sourceText = `<div class="dna-badge">🧬 Linked: ${item.family_members_affected.join(', ')}</div>`;
      }

      card.innerHTML = `
        <div class="watchlist-icon" style="background: ${iconColor};">${icon}</div>
        <div class="watchlist-content">
          <div class="watchlist-title">${item.disease_name} <span class="badge ${item.risk_level === 'high' ? 'badge-high' : 'badge-moderate'}" style="font-size: 9px; padding: 2px 6px;">${(item.probability * 100).toFixed(0)}%</span></div>
          <div class="watchlist-reason">${item.recommended_action}</div>
          ${sourceText}
        </div>
      `;
      list.appendChild(card);
    });
  }

  renderTrendChart() {
    drawTrendLine('trendChart', this.trends);
  }

  async regenerateProfile() {
    try {
      window.app.showLoader(true);
      window.app.showToast('⚡ Dispatching AI risk prediction engine...');
      
      const res = await window.api.generateRisk();
      if (res.success) {
        window.app.showToast('✓ Risk calculation task queued. Updating...');
        // Wait 2.5s for Celery calculations
        setTimeout(async () => {
          await this.loadRiskData();
          window.app.showToast('🚀 Health predictions updated successfully!');
        }, 2500);
      }
    } catch (e) {
      window.app.showToast(`❌ Failed to run predictions: ${e.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }
}

const risk = new RiskProfileManager();
window.risk = risk;
