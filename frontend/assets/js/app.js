class GenHealthApp {
  constructor() {
    this.currentPage = 'dashboard';
    this.isDark = localStorage.getItem(CONFIG.DARK_MODE_KEY) === 'true';
    this.tooltip = null;
  }

  async init() {
    // 1. Setup online/offline banners
    this.setupOfflineBanner();

    // 2. Setup Dark Mode theme
    this.applyTheme();

    // 3. Setup global hover tooltip
    this.createTooltipElement();

    // 4. Setup hash change router
    window.addEventListener('hashchange', () => this.handleRouting());

    // 5. Check user session
    await this.checkAuthAndStart();
  }

  setupOfflineBanner() {
    const banner = document.createElement('div');
    banner.id = 'offlineBanner';
    banner.className = 'offline-banner';
    banner.textContent = "You're offline — showing cached data.";
    document.body.appendChild(banner);

    const updateOnlineStatus = () => {
      if (navigator.onLine) {
        banner.style.display = 'none';
        this.showToast('📶 You are back online!');
      } else {
        banner.style.display = 'block';
        this.showToast('⚠️ Network connection lost. Offline mode active.');
      }
    };

    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);

    // Initial check
    if (!navigator.onLine) {
      banner.style.display = 'block';
    }
  }

  applyTheme() {
    if (this.isDark) {
      document.body.classList.add('dark');
    } else {
      document.body.classList.remove('dark');
    }
    const dt = document.getElementById('darkModeToggle');
    if (dt) dt.checked = this.isDark;
  }

  toggleDarkMode() {
    this.isDark = !this.isDark;
    localStorage.setItem(CONFIG.DARK_MODE_KEY, this.isDark);
    this.applyTheme();
  }

  createTooltipElement() {
    const tooltip = document.createElement('div');
    tooltip.id = 'globalTooltip';
    tooltip.style.position = 'fixed';
    tooltip.style.background = 'var(--color-primary)';
    tooltip.style.color = '#ffffff';
    tooltip.style.padding = '6px 12px';
    tooltip.style.borderRadius = '6px';
    tooltip.style.fontSize = '11px';
    tooltip.style.fontWeight = '500';
    tooltip.style.zIndex = '1000';
    tooltip.style.display = 'none';
    tooltip.style.pointerEvents = 'none';
    tooltip.style.boxShadow = '0 4px 12px rgba(10,37,64,0.15)';
    document.body.appendChild(tooltip);
    this.tooltip = tooltip;
  }

  showTooltip(event, text) {
    if (!this.tooltip) return;
    this.tooltip.textContent = text;
    this.tooltip.style.display = 'block';
    this.tooltip.style.left = `${event.clientX + 12}px`;
    this.tooltip.style.top = `${event.clientY + 12}px`;
  }

  hideTooltip() {
    if (this.tooltip) {
      this.tooltip.style.display = 'none';
    }
  }

  showLoader(show) {
    let loader = document.getElementById('appLoader');
    if (!loader) {
      loader = document.createElement('div');
      loader.id = 'appLoader';
      loader.style.position = 'fixed';
      loader.style.inset = '0';
      loader.style.background = 'rgba(255,255,255,0.4)';
      loader.style.zIndex = '999';
      loader.style.display = 'flex';
      loader.style.alignItems = 'center';
      loader.style.justifyContent = 'center';
      loader.innerHTML = `
        <svg class="dna-spinner" width="60" height="60" viewBox="0 0 80 80" fill="none">
          <circle cx="40" cy="40" r="10" fill="var(--color-accent)"></circle>
        </svg>
      `;
      document.body.appendChild(loader);
    }
    loader.style.display = show ? 'flex' : 'none';
  }

  showToast(msg) {
    const t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.style.opacity = '1';
    t.style.transform = 'translateX(-50%) translateY(0)';
    setTimeout(() => {
      t.style.opacity = '0';
      t.style.transform = 'translateX(-50%) translateY(20px)';
    }, 2500);
  }

  async checkAuthAndStart() {
    const token = window.api.getToken();
    const hash = window.location.hash;

    // Check for incoming invite token in URL parameters first
    const urlParams = new URLSearchParams(window.location.search);
    const inviteToken = urlParams.get('invite');
    if (inviteToken) {
      window.location.hash = `#invite-${inviteToken}`;
      return;
    }

    if (!token) {
      if (hash === '#signup') {
        window.location.hash = '#signup';
      } else {
        window.location.hash = '#login';
      }
      this.handleRouting();
    } else {
      try {
        await window.api.getMe();
        this.showAppShell();
        
        // Initial routing page from hash or default dashboard
        const defaultPage = hash ? hash.replace('#', '') : 'dashboard';
        this.navigateTo(defaultPage);
      } catch (e) {
        window.location.hash = '#login';
        this.handleRouting();
      }
    }
  }

  showAppShell() {
    document.getElementById('login-screen').classList.remove('active');
    document.getElementById('login-screen').style.display = 'none';

    const shell = document.getElementById('app-shell');
    shell.classList.add('active');
    shell.style.display = 'flex';
  }

  showAuthScreen() {
    document.getElementById('app-shell').classList.remove('active');
    document.getElementById('app-shell').style.display = 'none';

    const loginScreen = document.getElementById('login-screen');
    loginScreen.classList.add('active');
    loginScreen.style.display = 'flex';
  }

  async handleRouting() {
    const hash = window.location.hash || '#dashboard';
    
    // Auth Routes
    if (hash === '#login') {
      this.showAuthScreen();
      await this.loadAuthPage('login');
      return;
    }
    
    if (hash === '#signup') {
      this.showAuthScreen();
      await this.loadAuthPage('signup');
      return;
    }

    if (hash === '#onboarding') {
      this.showAuthScreen();
      await this.loadAuthPage('onboarding');
      return;
    }

    if (hash.startsWith('#invite-')) {
      const token = hash.replace('#invite-', '');
      this.showAuthScreen();
      await this.loadInviteLanding(token);
      return;
    }

    // App dashboard routing
    const pageName = hash.replace('#', '');
    const token = window.api.getToken();
    
    if (!token) {
      window.location.hash = '#login';
      return;
    }

    this.showAppShell();
    this.navigateTo(pageName);
  }

  async loadAuthPage(pageName) {
    try {
      this.showLoader(true);
      const res = await fetch(`pages/${pageName}.html`);
      const html = await res.text();
      document.getElementById('login-screen').innerHTML = html;

      // Populate onboarding defaults if Step 1 is loaded
      if (pageName === 'onboarding') {
        const user = window.api.getUser();
        if (user) {
          const genderSel = document.getElementById('onboardGender');
          const bloodSel = document.getElementById('onboardBlood');
          if (genderSel && user.gender) genderSel.value = user.gender;
          if (bloodSel && user.blood_group) bloodSel.value = user.blood_group;
        }
      }
    } catch (e) {
      this.showToast('❌ Error loading login pages.');
    } finally {
      this.showLoader(false);
    }
  }

  async loadInviteLanding(token) {
    try {
      this.showLoader(true);
      const res = await window.api.getInviteDetails(token);
      if (res.success && res.data) {
        const d = res.data;
        document.getElementById('login-screen').innerHTML = `
          <div class="login-left" style="background: linear-gradient(135deg, #8B5CF6 0%, #1a4a7a 100%);">
            <div class="login-left-content">
              <h1>Generational Health Connection</h1>
              <p>Securely link your health history to map familial patterns and discover early risk preventions.</p>
            </div>
          </div>
          <div class="login-right">
            <div class="login-form-card">
              <div class="login-logo">
                <div class="login-logo-icon" style="background:linear-gradient(135deg, #8B5CF6, #0097A7);"><span style="color:#fff;">🧬</span></div>
                <div class="login-logo-text">GenHealth AI<span>Family Linking</span></div>
              </div>
              <div class="login-title">Join Family Tree</div>
              <div class="login-subtitle"><strong>${d.inviter_name}</strong> has added you as their <strong>${d.relationship.replace('_', ' ')}</strong> on GenHealth.</div>
              
              <div style="background:rgba(139,92,246,0.06); border:1px solid rgba(139,92,246,0.2); padding:16px; border-radius:12px; font-size:13px; color:var(--color-muted); line-height:1.5; margin-bottom:24px;">
                🔐 <strong>Privacy Explanation:</strong> Linking your profile shares diagnosed conditions to compute disease risks, but keeps your raw prescription files strictly private.
              </div>

              <form id="inviteAcceptForm" onsubmit="app.handleInviteAccept(event, '${token}')">
                <div class="input-group">
                  <label class="input-label" for="inviteName">Full Name</label>
                  <input type="text" id="inviteName" class="input-field" required value="${d.inviter_name ? '' : ''}">
                </div>
                <div class="input-group">
                  <label class="input-label" for="inviteEmail">Email</label>
                  <input type="email" id="inviteEmail" class="input-field" required>
                </div>
                <div class="input-group">
                  <label class="input-label" for="invitePassword">Password</label>
                  <input type="password" id="invitePassword" class="input-field" required placeholder="Choose a secure password">
                </div>
                <button class="login-submit-btn" type="submit" style="background:linear-gradient(135deg, #8B5CF6, #0097A7);">Create Account & Link →</button>
              </form>
            </div>
          </div>
        `;
      }
    } catch (e) {
      this.showToast('❌ Invite link is invalid, expired, or already used.');
      window.location.hash = '#login';
    } finally {
      this.showLoader(false);
    }
  }

  async handleInviteAccept(event, token) {
    event.preventDefault();
    const name = document.getElementById('inviteName').value.trim();
    const email = document.getElementById('inviteEmail').value.trim();
    const password = document.getElementById('invitePassword').value;

    try {
      this.showLoader(true);
      const res = await window.api.acceptInvite(token, {
        full_name: name,
        email,
        password
      });

      if (res.success) {
        this.showToast('✅ Account created and family tree linked successfully!');
        window.location.hash = '#onboarding';
      }
    } catch (e) {
      this.showToast(`❌ Connection failed: ${e.message}`);
    } finally {
      this.showLoader(false);
    }
  }

  navigateTo(page) {
    this.currentPage = page;
    
    // De-activate all page containers, activate current
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById(`page-${page}`);
    if (target) target.classList.add('active');

    // Update active nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.toggle('active', item.dataset.page === page);
    });
    document.querySelectorAll('.bottom-nav-item').forEach(item => {
      item.classList.toggle('active', item.dataset.page === page);
    });

    // Populate user profile info in header and settings
    this.syncProfileUI();

    // Trigger page-specific initializers
    if (page === 'dashboard') this.initDashboard();
    if (page === 'records') window.records.loadRecords(1);
    if (page === 'upload') window.uploader.init();
    if (page === 'risk') window.risk.loadRiskData();
    if (page === 'family') window.family.loadFamilyData();
    if (page === 'recommendations') window.recommendations.loadRecommendations();
    if (page === 'doctor') this.initDoctorPortal();
    if (page === 'settings') {
      const dt = document.getElementById('darkModeToggle');
      if (dt) dt.checked = this.isDark;
    }

    // Scroll main body wrapper to top
    const wrapper = document.getElementById('content-area');
    if (wrapper) wrapper.scrollTop = 0;
  }

  syncProfileUI() {
    const user = window.api.getUser();
    if (!user) return;

    // Header username initials
    const avatar = document.getElementById('userAvatarHeader');
    if (avatar) {
      const initials = user.full_name.split(' ').map(p => p[0]).join('').toUpperCase();
      avatar.textContent = initials;
    }

    // Settings Profile segment
    const setAvatar = document.getElementById('profileAvatarSettings');
    const setName = document.getElementById('profileNameSettings');
    const setSub = document.getElementById('profileSubSettings');

    if (setAvatar) {
      setAvatar.textContent = user.full_name.split(' ').map(p => p[0]).join('').toUpperCase();
    }
    if (setName) setName.textContent = user.full_name;
    if (setSub) {
      const ageStr = user.date_of_birth ? `${this.calculateAge(user.date_of_birth)}` : 'Age unknown';
      setSub.innerHTML = `${ageStr} · Blood Group: ${user.blood_group || 'None'} · ${user.email}`;
    }
  }

  calculateAge(dobString) {
    const dob = new Date(dobString);
    const diff = Date.now() - dob.getTime();
    const ageDate = new Date(diff);
    return Math.abs(ageDate.getUTCFullYear() - 1970);
  }

  async initDashboard() {
    // Current date label
    const dateEl = document.getElementById('currentDate');
    if (dateEl) {
      const now = new Date();
      dateEl.textContent = now.toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    }

    // Dashboard Greeting
    const greetingText = document.getElementById('greetingText');
    const user = window.api.getUser();
    if (greetingText && user) {
      greetingText.textContent = `Hello, ${user.full_name.split(' ')[0]} 👋`;
    }

    try {
      // Fetch health score and predictions to show overview on dashboard
      const [scoreRes, riskRes] = await Promise.all([
        window.api.getHealthScore(),
        window.api.getRiskProfile()
      ]);

      if (scoreRes.success && scoreRes.data) {
        drawHealthGauge('healthGaugeDashboard', scoreRes.data.score);
      }

      if (riskRes.success && riskRes.data) {
        const list = document.getElementById('dashboardRiskList');
        if (list) {
          list.innerHTML = '';
          const topPredictions = (riskRes.data.predictions || []).slice(0, 3);
          
          if (topPredictions.length === 0) {
            list.innerHTML = '<div style="font-size:12px; color:var(--color-muted);">No predictive risks. Onboard parameters to view.</div>';
          }

          topPredictions.forEach(pred => {
            const item = document.createElement('div');
            item.className = 'risk-item';
            
            const color = pred.risk_level === 'high' ? 'var(--color-risk-high)' : pred.risk_level === 'moderate' ? 'var(--color-risk-moderate)' : 'var(--color-risk-low)';
            const pct = (pred.probability * 100).toFixed(0);

            item.innerHTML = `
              <div class="risk-dot" style="background: ${color};"></div>
              <div class="risk-name">${pred.disease_name}</div>
              <div class="risk-pct" style="color: ${color};">${pct}%</div>
            `;
            list.appendChild(item);
          });
        }
      }

      // Load timeline events
      const timelineRes = await window.api.getTimeline();
      if (timelineRes.success && timelineRes.data) {
        const events = (timelineRes.data.events || []).slice(0, 3);
        const timelineList = document.getElementById('dashboardTimeline');
        
        if (timelineList) {
          timelineList.innerHTML = '';
          
          if (events.length === 0) {
            timelineList.innerHTML = '<div style="font-size:12px; color:var(--color-muted);">No recent logs.</div>';
          }

          events.forEach((ev, idx) => {
            const item = document.createElement('div');
            item.className = 'timeline-item';
            const formattedDate = ev.record_date 
              ? new Date(ev.record_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
              : 'Unknown date';

            item.innerHTML = `
              <div class="timeline-dot-wrap">
                <div class="timeline-dot"></div>
                ${idx < events.length - 1 ? '<div class="timeline-line"></div>' : ''}
              </div>
              <div class="timeline-content">
                <div class="timeline-date">${formattedDate}</div>
                <div class="timeline-title">${ev.title}</div>
              </div>
            `;
            timelineList.appendChild(item);
          });
        }
      }

    } catch (e) {
      console.warn('Dashboard initialization warnings:', e);
    }
  }

  // Doctor Portal Logic
  async initDoctorPortal() {
    const list = document.getElementById('patientsList');
    if (!list) return;

    list.innerHTML = '<div class="skeleton-card"><div class="skeleton skeleton-text"></div></div>';

    try {
      const res = await window.api.getPatients();
      if (res.success && res.data) {
        const patients = res.data.patients || [];
        list.innerHTML = '';

        if (patients.length === 0) {
          list.innerHTML = '<div style="font-size:13px; color:var(--color-muted); padding:20px; text-align:center;">No patients assigned or active access grants.</div>';
          return;
        }

        patients.forEach(row => {
          const pat = row.patient;
          const card = document.createElement('div');
          card.className = 'patient-card';
          card.style.cursor = 'pointer';
          card.style.background = 'var(--color-surface)';
          card.style.border = '1px solid var(--color-border)';
          card.style.color = 'var(--color-text)';
          card.style.padding = '16px';
          card.style.borderRadius = 'var(--radius-card)';
          card.style.marginBottom = '12px';
          card.style.display = 'flex';
          card.style.alignItems = 'center';
          card.style.gap = '16px';

          const initials = pat.full_name.split(' ').map(p => p[0]).join('').toUpperCase();
          const expiresDate = row.expires_at ? new Date(row.expires_at).toLocaleDateString('en-IN') : 'Ongoing';

          card.innerHTML = `
            <div class="patient-avatar" style="background:var(--color-accent); color:#fff; font-size:16px; width:44px; height:44px;">${initials}</div>
            <div style="flex:1;">
              <div style="font-weight:700; font-size:15px; font-family:var(--font-display);">${pat.full_name}</div>
              <div style="font-size:12px; color:var(--color-muted); margin-top:2px;">Age: ${this.calculateAge(pat.date_of_birth)} · Blood: ${pat.blood_group} · Health Score: <strong>${row.health_score}</strong></div>
            </div>
            <div style="text-align:right; font-size:11px; color:var(--color-muted);">
              Access level: ${row.access_level}<br>Expires: ${expiresDate}
            </div>
          `;

          card.addEventListener('click', () => this.showPatientDetails(pat.id));
          list.appendChild(card);
        });
      }
    } catch (e) {
      list.innerHTML = `<div style="font-size:13px; color:var(--color-risk-high);">Access denied: ${e.message}</div>`;
    }
  }

  async showPatientDetails(patientId) {
    try {
      this.showLoader(true);
      const res = await window.api.getPatientSummary(patientId);
      if (res.success && res.data) {
        const d = res.data;
        const pat = d.patient;
        
        document.getElementById('detailTitle').textContent = pat.full_name;
        const content = document.getElementById('detailContent');

        const activeRisksHtml = d.active_risks.length > 0
          ? d.active_risks.map(r => `<span class="badge ${r.risk_level === 'high' ? 'badge-high' : 'badge-moderate'}" style="margin-right:6px; margin-bottom:6px;">${r.disease_name}: ${(r.probability * 100).toFixed(0)}%</span>`).join('')
          : '<span style="font-size:13px; color:var(--color-muted);">No predictive risks calculated.</span>';

        content.innerHTML = `
          <div class="detail-field">
            <div class="detail-field-label">Health Score</div>
            <div class="detail-field-value" style="font-size:22px; font-weight:700; color:var(--color-accent);">${d.health_score}/100</div>
          </div>
          <div class="detail-field">
            <div class="detail-field-label">Chief Complaint AI Assist</div>
            <div style="margin-top:6px; display:flex; gap:8px;">
              <input type="text" id="chiefComplaintInput" class="input-field" placeholder="Enter patient symptom..." style="height:36px; font-size:12px;">
              <button class="btn btn-primary" style="height:36px; padding:0 12px; font-size:12px;" onclick="app.analyzePatientComplaint('${pat.id}')">Analyze</button>
            </div>
          </div>
          <div id="aiSymptomResult" style="margin-top:12px;"></div>
          <div class="detail-field">
            <div class="detail-field-label">Active Risks</div>
            <div style="margin-top:6px;">${activeRisksHtml}</div>
          </div>
        `;

        document.getElementById('detailOverlay').classList.add('active');
      }
    } catch (e) {
      this.showToast(`❌ Could not retrieve details: ${e.message}`);
    } finally {
      this.showLoader(false);
    }
  }

  async analyzePatientComplaint(patientId) {
    const input = document.getElementById('chiefComplaintInput');
    const resultDiv = document.getElementById('aiSymptomResult');
    if (!input || !input.value.trim() || !resultDiv) return;

    try {
      this.showLoader(true);
      resultDiv.innerHTML = '<div class="skeleton-card"><div class="skeleton skeleton-text"></div></div>';
      
      const res = await window.api.getRelevantRecords(patientId, input.value.trim());
      if (res.success && res.data) {
        const records = res.data.records || [];
        resultDiv.innerHTML = '<div style="font-weight:600; font-size:11px; color:var(--color-muted); text-transform:uppercase; margin-bottom:8px;">AI Surfaced Relevant Records</div>';
        
        if (records.length === 0) {
          resultDiv.innerHTML += '<div style="font-size:12px; color:var(--color-muted);">No highly relevant history matches.</div>';
          return;
        }

        records.forEach(rec => {
          resultDiv.innerHTML += `
            <div style="padding: 10px; background:rgba(0,196,154,0.05); border:1px solid rgba(0,196,154,0.2); border-radius:8px; margin-bottom:8px; font-size:12px;">
              <strong>${rec.record_type.replace('_', ' ').toUpperCase()}</strong><br>
              <span style="color:var(--color-muted);">Date: ${rec.record_date || 'N/A'}</span>
            </div>
          `;
        });
      }
    } catch (e) {
      resultDiv.innerHTML = `<span style="font-size:12px; color:var(--color-risk-high);">Analysis failed: ${e.message}</span>`;
    } finally {
      this.showLoader(false);
    }
  }

  closeDetail(e) {
    if (!e || e.target === document.getElementById('detailOverlay')) {
      document.getElementById('detailOverlay').classList.remove('active');
    }
  }

  async deleteAccount() {
    const user = window.api.getUser();
    if (!user) return;

    const confirmMessage = `WARNING: Are you sure you want to permanently delete your account?\nAll your personal health records, family tree connections, and predictions will be deleted forever.\n\nType your email "${user.email}" to confirm:`;
    const confirmation = prompt(confirmMessage);
    if (confirmation !== user.email) {
      if (confirmation !== null) {
        this.showToast('⚠️ Email verification failed. Account deletion cancelled.');
      }
      return;
    }

    try {
      this.showLoader(true);
      const res = await window.api.request('DELETE', `/users/${user.id}`);
      if (res.success) {
        this.showToast('✓ Account deleted successfully.');
        window.api.clearTokens();
        setTimeout(() => {
          window.location.hash = '#login';
        }, 1500);
      }
    } catch (e) {
      this.showToast(`❌ Deletion failed: ${e.message}`);
    } finally {
      this.showLoader(false);
    }
  }

  async handleLogout() {
    this.showLoader(true);
    try {
      await window.api.logout();
      this.showToast('Logged out.');
      window.location.hash = '#login';
    } catch (e) {
      window.location.hash = '#login';
    } finally {
      this.showLoader(false);
    }
  }
}

const app = new GenHealthApp();
window.app = app;

document.addEventListener('DOMContentLoaded', () => app.init());
