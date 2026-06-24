/**
 * GenHealth AI — API Client Layer
 *
 * Central HTTP client that:
 * - Manages base URL configuration
 * - Attaches Authorization headers automatically
 * - Handles token refresh on 401 responses
 * - Returns consistent {success, data, message} or throws ApiError
 */

const API_BASE_URL = "http://localhost:8000/api/v1";

// ─── Token Management ────────────────────────────────────────────────────────

const TokenStore = {
  getAccess: () => localStorage.getItem("gh_access_token"),
  getRefresh: () => localStorage.getItem("gh_refresh_token"),
  setTokens: (access, refresh) => {
    localStorage.setItem("gh_access_token", access);
    if (refresh) localStorage.setItem("gh_refresh_token", refresh);
  },
  clear: () => {
    localStorage.removeItem("gh_access_token");
    localStorage.removeItem("gh_refresh_token");
    localStorage.removeItem("gh_user");
  },
};

// ─── ApiError Class ───────────────────────────────────────────────────────────

class ApiError extends Error {
  /**
   * @param {string} message - Human-readable error message
   * @param {string} code    - Machine-readable error code
   * @param {number} status  - HTTP status code
   */
  constructor(message, code, status) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

// ─── Core Fetch Wrapper ──────────────────────────────────────────────────────

let _isRefreshing = false;
let _refreshQueue = [];

/**
 * Make an authenticated API request.
 *
 * Automatically:
 * - Attaches the Bearer token
 * - Retries once with a refreshed token on 401
 * - Throws ApiError on non-success responses
 *
 * @param {string} endpoint  - API path (e.g. "/auth/me")
 * @param {RequestInit} opts - Fetch options (method, body, headers)
 * @returns {Promise<any>}   - The `data` field from the response envelope
 */
async function apiFetch(endpoint, opts = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    ...opts.headers,
  };

  const accessToken = TokenStore.getAccess();
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const response = await fetch(url, { ...opts, headers });
  const json = await response.json().catch(() => ({}));

  // Handle 401 — attempt token refresh
  if (response.status === 401 && !opts._retried) {
    const refreshed = await _tryRefreshToken();
    if (refreshed) {
      return apiFetch(endpoint, { ...opts, _retried: true });
    } else {
      TokenStore.clear();
      window.dispatchEvent(new CustomEvent("gh:logout"));
      throw new ApiError(json.error || "Session expired.", json.code || "UNAUTHORIZED", 401);
    }
  }

  if (!json.success) {
    throw new ApiError(
      json.error || "An unexpected error occurred.",
      json.code || "UNKNOWN_ERROR",
      response.status,
    );
  }

  return json.data;
}

/**
 * Attempt to refresh the access token using the stored refresh token.
 * @returns {Promise<boolean>} True if refresh succeeded.
 */
async function _tryRefreshToken() {
  const refreshToken = TokenStore.getRefresh();
  if (!refreshToken) return false;

  if (_isRefreshing) {
    // Queue this request until refresh completes
    return new Promise((resolve) => _refreshQueue.push(resolve));
  }

  _isRefreshing = true;
  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    const json = await response.json();
    if (json.success && json.data?.access_token) {
      TokenStore.setTokens(json.data.access_token, json.data.refresh_token);
      _refreshQueue.forEach((resolve) => resolve(true));
      return true;
    }
  } catch (e) {
    console.error("Token refresh failed:", e);
  } finally {
    _isRefreshing = false;
    _refreshQueue = [];
  }
  return false;
}

// ─── Convenience Helpers ─────────────────────────────────────────────────────

const api = {
  get: (endpoint, opts = {}) => apiFetch(endpoint, { method: "GET", ...opts }),

  post: (endpoint, body, opts = {}) =>
    apiFetch(endpoint, {
      method: "POST",
      body: JSON.stringify(body),
      ...opts,
    }),

  patch: (endpoint, body, opts = {}) =>
    apiFetch(endpoint, {
      method: "PATCH",
      body: JSON.stringify(body),
      ...opts,
    }),

  delete: (endpoint, opts = {}) =>
    apiFetch(endpoint, { method: "DELETE", ...opts }),

  /**
   * Upload a file using multipart/form-data.
   * @param {string} endpoint
   * @param {FormData} formData
   */
  upload: (endpoint, formData) =>
    apiFetch(endpoint, {
      method: "POST",
      headers: {}, // Let browser set Content-Type with boundary
      body: formData,
    }),
};

// ─── Named Endpoint Modules ──────────────────────────────────────────────────

/** Auth endpoints */
const authApi = {
  signup: (data) => api.post("/auth/signup", data),
  login: (email, password) => api.post("/auth/login", { email, password }),
  refresh: (refreshToken) => api.post("/auth/refresh", { refresh_token: refreshToken }),
  logout: () => api.post("/auth/logout"),
  me: () => api.get("/auth/me"),
  updateProfile: (data) => api.patch("/auth/me", data),
  verifyEmail: (email, otp) => api.post("/auth/verify-email", { email, otp }),
  forgotPassword: (email) => api.post("/auth/forgot-password", { email }),
  resetPassword: (token, newPassword) =>
    api.post("/auth/reset-password", { token, new_password: newPassword }),
};

/** Family endpoints */
const familyApi = {
  listMembers: () => api.get("/family/members"),
  addMember: (data) => api.post("/family/members", data),
  updateMember: (id, data) => api.patch(`/family/members/${id}`, data),
  deleteMember: (id) => api.delete(`/family/members/${id}`),
  sendInvite: (data) => api.post("/family/invite", data),
  getTree: () => api.get("/family/tree"),
  getSharedRisks: () => api.get("/family/shared-risks"),
};

/** Records endpoints */
const recordsApi = {
  list: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api.get(`/records/?${qs}`);
  },
  get: (id) => api.get(`/records/${id}`),
  verify: (id, data) => api.patch(`/records/${id}/verify`, data),
  delete: (id) => api.delete(`/records/${id}`),
  timeline: () => api.get("/records/timeline"),
  entities: (type) => api.get(`/records/entities${type ? `?entity_type=${type}` : ""}`),
};

/** Upload endpoints */
const uploadApi = {
  uploadFile: (file, recordType = "prescription", familyMemberId = null) => {
    const form = new FormData();
    form.append("file", file);
    form.append("record_type", recordType);
    if (familyMemberId) form.append("family_member_id", familyMemberId);
    return api.upload("/upload/", form);
  },
  taskStatus: (taskId) => api.get(`/upload/status/${taskId}`),
};

/** Risk endpoints */
const riskApi = {
  profile: () => api.get("/risk/profile"),
  predictions: () => api.get("/risk/predictions"),
  generate: (data = {}) => api.post("/risk/generate", data),
  diseaseDetail: (name) => api.get(`/risk/predictions/${encodeURIComponent(name)}`),
  familyRisk: () => api.get("/risk/family-risk"),
  watchlist: (limit = 5) => api.get(`/risk/watchlist?limit=${limit}`),
};

/** Insights endpoints */
const insightsApi = {
  healthScore: () => api.get("/insights/health-score"),
  trends: (months = 12) => api.get(`/insights/trends?months=${months}`),
  summary: () => api.get("/insights/summary"),
  recommendations: () => api.get("/insights/recommendations"),
  heatmap: (months = 12) => api.get(`/insights/heatmap?months=${months}`),
};

/** Invite endpoints (public) */
const inviteApi = {
  validate: (token) => api.get(`/invite/${token}`),
  accept: (token, data) => api.post(`/invite/${token}/accept`, data),
};

// Export for use in other modules
window.GenHealthAPI = {
  TokenStore,
  ApiError,
  api,
  auth: authApi,
  family: familyApi,
  records: recordsApi,
  upload: uploadApi,
  risk: riskApi,
  insights: insightsApi,
  invite: inviteApi,
};
