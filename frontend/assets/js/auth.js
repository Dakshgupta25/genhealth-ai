/**
 * GenHealth AI — Auth Module
 *
 * Handles:
 * - Login / signup / logout UI flows
 * - Token persistence in localStorage
 * - Auth state management
 * - Route guards for protected pages
 */

const Auth = (() => {
  const { auth, TokenStore } = window.GenHealthAPI;

  // ─── State ────────────────────────────────────────────────────────────────

  let _currentUser = null;

  function getCurrentUser() {
    if (_currentUser) return _currentUser;
    const stored = localStorage.getItem("gh_user");
    if (stored) {
      try { _currentUser = JSON.parse(stored); } catch (_) {}
    }
    return _currentUser;
  }

  function isLoggedIn() {
    return !!TokenStore.getAccess() && !!getCurrentUser();
  }

  // ─── Login ────────────────────────────────────────────────────────────────

  /**
   * Authenticate a user and persist tokens + profile.
   * @param {string} email
   * @param {string} password
   * @returns {Promise<object>} The user profile object
   */
  async function login(email, password) {
    const data = await auth.login(email, password);
    _storeSession(data);
    return data.user;
  }

  // ─── Signup ───────────────────────────────────────────────────────────────

  /**
   * Register a new account and automatically log them in.
   * @param {object} formData - {email, password, full_name, role, ...}
   * @returns {Promise<object>} The user profile object
   */
  async function signup(formData) {
    const data = await auth.signup(formData);
    _storeSession(data);
    return data.user;
  }

  // ─── Logout ───────────────────────────────────────────────────────────────

  /**
   * Log out the current user: call the API, then clear local state.
   */
  async function logout() {
    try {
      await auth.logout();
    } catch (_) {
      // Even if the API call fails, clear client-side state
    }
    _clearSession();
    window.dispatchEvent(new CustomEvent("gh:logout"));
  }

  // ─── Profile ──────────────────────────────────────────────────────────────

  /**
   * Fetch and cache the current user's profile from the API.
   * @returns {Promise<object>}
   */
  async function refreshProfile() {
    const data = await auth.me();
    _currentUser = data;
    localStorage.setItem("gh_user", JSON.stringify(data));
    return data;
  }

  /**
   * Update profile fields and refresh the cached user.
   * @param {object} updates
   */
  async function updateProfile(updates) {
    const data = await auth.updateProfile(updates);
    _currentUser = data;
    localStorage.setItem("gh_user", JSON.stringify(data));
    return data;
  }

  // ─── OTP ──────────────────────────────────────────────────────────────────

  /**
   * @param {string} email
   * @param {string} otp
   */
  async function verifyEmail(email, otp) {
    return auth.verifyEmail(email, otp);
  }

  // ─── Route Guard ──────────────────────────────────────────────────────────

  /**
   * Guard a page that requires authentication.
   * Redirects to login if not authenticated.
   */
  function requireAuth() {
    if (!isLoggedIn()) {
      window.location.href = "/pages/login.html";
    }
  }

  /**
   * Guard a page that requires a specific role.
   * @param {'patient'|'doctor'|'admin'} role
   */
  function requireRole(role) {
    requireAuth();
    const user = getCurrentUser();
    if (user && user.role !== role) {
      alert(`This page requires the '${role}' role.`);
      window.location.href = "/index.html";
    }
  }

  // ─── Private helpers ──────────────────────────────────────────────────────

  function _storeSession({ user, tokens }) {
    TokenStore.setTokens(tokens.access_token, tokens.refresh_token);
    _currentUser = user;
    localStorage.setItem("gh_user", JSON.stringify(user));
  }

  function _clearSession() {
    TokenStore.clear();
    _currentUser = null;
  }

  // Auto-logout on API 401 broadcast
  window.addEventListener("gh:logout", () => {
    _clearSession();
    if (!window.location.pathname.includes("login")) {
      window.location.href = "/pages/login.html";
    }
  });

  return {
    login,
    signup,
    logout,
    refreshProfile,
    updateProfile,
    verifyEmail,
    getCurrentUser,
    isLoggedIn,
    requireAuth,
    requireRole,
  };
})();

window.Auth = Auth;
