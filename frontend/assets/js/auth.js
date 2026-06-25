class GenHealthAuth {
  constructor() {
    this.currentRole = 'patient';
  }

  selectRole(role, element) {
    this.currentRole = role;
    document.querySelectorAll('#roleSelector .role-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    element.classList.add('active');
  }

  goToLogin() {
    window.location.hash = '#login';
  }

  goToSignup() {
    window.location.hash = '#signup';
  }

  handleGoogleLogin() {
    if (window.app && window.app.showToast) {
      window.app.showToast('ℹ️ Google Authentication stub triggered.');
    } else {
      alert('Google Authentication stub triggered.');
    }
  }

  checkPasswordStrength(password) {
    const container = document.getElementById('password-strength-container');
    const fill = document.getElementById('password-strength-fill');
    const text = document.getElementById('password-strength-text');

    if (!password) {
      container.style.display = 'none';
      return;
    }

    container.style.display = 'block';

    let score = 0;
    if (password.length >= 8) score += 25;
    if (/[a-z]/.test(password)) score += 25;
    if (/[A-Z]/.test(password)) score += 25;
    if (/[0-9]/.test(password)) score += 25;

    fill.style.width = `${score}%`;

    if (score < 50) {
      fill.style.background = 'var(--color-risk-high)';
      text.textContent = 'Weak password (must have 8+ chars, uppercase & digit)';
      text.style.color = 'var(--color-risk-high)';
    } else if (score < 100) {
      fill.style.background = 'var(--color-risk-moderate)';
      text.textContent = 'Moderate password (add uppercase / numbers)';
      text.style.color = 'var(--color-risk-moderate)';
    } else {
      fill.style.background = 'var(--color-risk-low)';
      text.textContent = 'Strong password!';
      text.style.color = 'var(--color-risk-low)';
    }
  }

  async handleLogin(event) {
    event.preventDefault();
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;

    if (!email || !password) {
      window.app.showToast('❌ Please fill all fields.');
      return;
    }

    try {
      window.app.showLoader(true);
      const res = await window.api.login(email, password);
      
      if (res.success) {
        window.app.showToast('✅ Welcome to GenHealth!');
        
        // Sync user role and profile
        const user = res.data.user;
        
        // If onboarding is incomplete, redirect there
        if (!user.gender || !user.blood_group) {
          window.location.hash = '#onboarding';
        } else {
          window.location.hash = '#dashboard';
        }
      }
    } catch (err) {
      window.app.showToast(`❌ Login failed: ${err.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }

  async handleSignup(event) {
    event.preventDefault();
    const fullName = document.getElementById('signupName').value.trim();
    const dob = document.getElementById('signupDob').value;
    const email = document.getElementById('signupEmail').value.trim();
    const password = document.getElementById('signupPassword').value;
    const bloodGroup = document.getElementById('signupBlood').value;
    const gender = document.getElementById('signupGender').value;

    if (!fullName || !dob || !email || !password) {
      window.app.showToast('❌ Please fill all required fields.');
      return;
    }

    // Password strength check
    if (!/[A-Z]/.test(password) || !/[0-9]/.test(password)) {
      window.app.showToast('❌ Password must contain at least one uppercase letter and one number.');
      return;
    }

    try {
      window.app.showLoader(true);
      const res = await window.api.signup({
        email,
        password,
        full_name: fullName,
        date_of_birth: dob,
        gender,
        blood_group: bloodGroup,
        role: this.currentRole
      });

      if (res.success) {
        window.app.showToast('✨ Account created successfully!');
        window.location.hash = '#onboarding';
      }
    } catch (err) {
      window.app.showToast(`❌ Sign Up failed: ${err.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }

  nextOnboardStep() {
    const step1 = document.getElementById('onboardStep1');
    const step2 = document.getElementById('onboardStep2');
    const indicator = document.getElementById('stepIndicator');
    const progress = document.getElementById('stepProgress');
    const progressBar = document.getElementById('onboardingProgressBar');

    step1.style.display = 'none';
    step2.style.display = 'block';
    indicator.textContent = 'Step 2 of 2: Preferences';
    progress.textContent = '100% Complete';
    progressBar.style.width = '100%';
  }

  prevOnboardStep() {
    const step1 = document.getElementById('onboardStep1');
    const step2 = document.getElementById('onboardStep2');
    const indicator = document.getElementById('stepIndicator');
    const progress = document.getElementById('stepProgress');
    const progressBar = document.getElementById('onboardingProgressBar');

    step2.style.display = 'none';
    step1.style.display = 'block';
    indicator.textContent = 'Step 1 of 2: Health Info';
    progress.textContent = '50% Complete';
    progressBar.style.width = '50%';
  }

  async handleOnboardingSubmit(event) {
    event.preventDefault();
    const phone = document.getElementById('onboardPhone').value.trim();
    const gender = document.getElementById('onboardGender').value;
    const bloodGroup = document.getElementById('onboardBlood').value;
    const consent = document.getElementById('onboardConsent').checked;

    if (!consent) {
      window.app.showToast('❌ You must consent to security storage to proceed.');
      return;
    }

    try {
      window.app.showLoader(true);
      const res = await window.api.updateProfile({
        phone: phone || null,
        gender,
        blood_group: bloodGroup
      });

      if (res.success) {
        // Trigger risk profile generation to baseline predictions
        try {
          await window.api.generateRisk();
        } catch (e) {
          console.warn('Initial risk generation task dispatch failed, non-blocking.', e);
        }
        window.app.showToast('🚀 Profile personalized successfully!');
        window.location.hash = '#dashboard';
      }
    } catch (err) {
      window.app.showToast(`❌ Onboarding failed: ${err.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }
}

const auth = new GenHealthAuth();
window.auth = auth;
