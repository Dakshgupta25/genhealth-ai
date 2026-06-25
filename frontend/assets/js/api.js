class GenHealthAPI {
  constructor(baseURL) {
    this.baseURL = baseURL;
    this.isRefreshing = false;
    this.refreshSubscribers = [];
  }

  // Token management
  getToken() {
    return localStorage.getItem(CONFIG.TOKEN_KEY);
  }

  getRefreshToken() {
    return localStorage.getItem(CONFIG.REFRESH_KEY);
  }

  setTokens(access, refresh) {
    localStorage.setItem(CONFIG.TOKEN_KEY, access);
    localStorage.setItem(CONFIG.REFRESH_KEY, refresh);
  }

  clearTokens() {
    localStorage.removeItem(CONFIG.TOKEN_KEY);
    localStorage.removeItem(CONFIG.REFRESH_KEY);
    localStorage.removeItem(CONFIG.USER_KEY);
  }

  getUser() {
    const userJson = localStorage.getItem(CONFIG.USER_KEY);
    try {
      return userJson ? JSON.parse(userJson) : null;
    } catch (e) {
      return null;
    }
  }

  setUser(user) {
    localStorage.setItem(CONFIG.USER_KEY, JSON.stringify(user));
  }

  // Subscribe to token refresh events
  subscribeTokenRefresh(cb) {
    this.refreshSubscribers.push(cb);
  }

  onRefreshed(token) {
    this.refreshSubscribers.map(cb => cb(token));
    this.refreshSubscribers = [];
  }

  // Core request method with auto-refresh on 401
  async request(method, path, body = null, isFormData = false) {
    const url = `${this.baseURL}${path}`;
    const headers = {};

    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    if (!isFormData) {
      headers['Content-Type'] = 'application/json';
    }

    const options = {
      method,
      headers,
    };

    if (body) {
      options.body = isFormData ? body : JSON.stringify(body);
    }

    try {
      const response = await fetch(url, options);

      // Handle 401: try refreshing token
      if (response.status === 401 && this.getRefreshToken() && path !== '/auth/refresh' && path !== '/auth/login') {
        try {
          const newAccessToken = await this.handleTokenRefresh();
          // Retry the request with the new access token
          headers['Authorization'] = `Bearer ${newAccessToken}`;
          const retryResponse = await fetch(url, options);
          return await this.parseResponse(retryResponse);
        } catch (refreshErr) {
          // Token refresh failed -> clear tokens and redirect to login
          this.clearTokens();
          window.location.hash = '#login';
          throw new Error('Session expired. Please log in again.');
        }
      }

      return await this.parseResponse(response);
    } catch (error) {
      console.error(`API request error on ${path}:`, error);
      throw error;
    }
  }

  async parseResponse(response) {
    const text = await response.text();
    let json = {};
    try {
      json = text ? JSON.parse(text) : {};
    } catch (e) {
      json = { success: response.ok, error: 'Failed to parse JSON response' };
    }

    if (!response.ok) {
      const errMessage = json.detail && json.detail.error ? json.detail.error : (json.message || response.statusText || 'API Error');
      const errCode = json.detail && json.detail.code ? json.detail.code : 'API_ERROR';
      const error = new Error(errMessage);
      error.status = response.status;
      error.code = errCode;
      throw error;
    }

    return json;
  }

  async handleTokenRefresh() {
    if (this.isRefreshing) {
      return new Promise((resolve) => {
        this.subscribeTokenRefresh(token => {
          resolve(token);
        });
      });
    }

    this.isRefreshing = true;

    try {
      const refreshPayload = { refresh_token: this.getRefreshToken() };
      const response = await fetch(`${this.baseURL}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(refreshPayload)
      });

      if (!response.ok) {
        throw new Error('Failed to refresh token');
      }

      const json = await response.json();
      const tokens = json.data;
      this.setTokens(tokens.access_token, tokens.refresh_token);
      this.isRefreshing = false;
      this.onRefreshed(tokens.access_token);
      return tokens.access_token;
    } catch (err) {
      this.isRefreshing = false;
      throw err;
    }
  }

  // Auth Endpoints
  async login(email, password) {
    const res = await this.request('POST', '/auth/login', { email, password });
    if (res.success && res.data) {
      this.setTokens(res.data.tokens.access_token, res.data.tokens.refresh_token);
      this.setUser(res.data.user);
    }
    return res;
  }

  async signup(data) {
    // data: { email, password, full_name, date_of_birth, gender, blood_group, role }
    const res = await this.request('POST', '/auth/signup', data);
    if (res.success && res.data) {
      this.setTokens(res.data.tokens.access_token, res.data.tokens.refresh_token);
      this.setUser(res.data.user);
    }
    return res;
  }

  async verifyEmail(email, otp) {
    return await this.request('POST', '/auth/verify-email', { email, otp });
  }

  async getMe() {
    const res = await this.request('GET', '/auth/me');
    if (res.success && res.data) {
      this.setUser(res.data);
    }
    return res;
  }

  async updateProfile(data) {
    // data: { full_name, phone, date_of_birth, gender, blood_group }
    const res = await this.request('PATCH', '/auth/me', data);
    if (res.success && res.data) {
      this.setUser(res.data);
    }
    return res;
  }

  async logout() {
    try {
      await this.request('POST', '/auth/logout');
    } catch (e) {
      console.warn('Logout endpoint failed or user already logged out', e);
    } finally {
      this.clearTokens();
    }
  }

  // Family Endpoints
  async getFamilyMembers() {
    return await this.request('GET', '/family/members');
  }

  async addFamilyMember(data) {
    // data: { name, relationship, gender, date_of_birth, is_deceased }
    return await this.request('POST', '/family/members', data);
  }

  async updateFamilyMember(memberId, data) {
    return await this.request('PATCH', `/family/members/${memberId}`, data);
  }

  async deleteFamilyMember(memberId) {
    return await this.request('DELETE', `/family/members/${memberId}`);
  }

  async sendFamilyInvite(familyMemberId, email, phone) {
    // data: { family_member_id, invitee_email, invitee_phone }
    return await this.request('POST', '/family/invite', {
      family_member_id: familyMemberId,
      invitee_email: email || null,
      invitee_phone: phone || null
    });
  }

  async getInviteDetails(token) {
    // public endpoint GET /api/v1/invite/:token
    // Wait, the router prefix is "/invite" in main.py, so it's "/invite/{token}"
    return await this.request('GET', `/invite/${token}`);
  }

  async acceptInvite(token, data) {
    // POST /api/v1/invite/:token/accept
    // data: { email, password, full_name, date_of_birth, gender }
    const res = await this.request('POST', `/invite/${token}/accept`, data);
    if (res.success && res.data) {
      this.setTokens(res.data.tokens.access_token, res.data.tokens.refresh_token);
      this.setUser(res.data.user);
    }
    return res;
  }

  async getFamilyTree() {
    return await this.request('GET', '/family/tree');
  }

  async getSharedRisks() {
    return await this.request('GET', '/family/shared-risks');
  }

  // Records Endpoints
  async getRecords(filters = {}) {
    // filters: { page, per_page, record_type, include_family }
    const params = new URLSearchParams();
    Object.keys(filters).forEach(key => {
      if (filters[key] !== undefined && filters[key] !== null) {
        params.append(key, filters[key]);
      }
    });
    const qs = params.toString() ? `?${params.toString()}` : '';
    return await this.request('GET', `/records/${qs}`);
  }

  async getRecord(id) {
    return await this.request('GET', `/records/${id}`);
  }

  async uploadPrescription(file, recordType = 'prescription', familyMemberId = null) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('record_type', recordType);
    if (familyMemberId) {
      formData.append('family_member_id', familyMemberId);
    }
    return await this.request('POST', '/upload/', formData, true);
  }

  async verifyRecord(id, corrections = null, structuredData = null) {
    // body: { corrections: [{entity_id, corrected_value}], structured_data: {} }
    return await this.request('PATCH', `/records/${id}/verify`, { corrections, structured_data: structuredData });
  }

  async getTimeline() {
    return await this.request('GET', '/records/timeline');
  }

  // Risk Endpoints
  async getRiskProfile() {
    return await this.request('GET', '/risk/profile');
  }

  async getRiskPredictions() {
    return await this.request('GET', '/risk/predictions');
  }

  async generateRisk(diseaseName = null, force = true) {
    return await this.request('POST', '/risk/generate', { disease_name: diseaseName, force });
  }

  async getWatchlist(limit = 5) {
    return await this.request('GET', `/risk/watchlist?limit=${limit}`);
  }

  // Insights Endpoints
  async getHealthScore() {
    return await this.request('GET', '/insights/health-score');
  }

  async getTrends(months = 12) {
    return await this.request('GET', `/insights/trends?months=${months}`);
  }

  async getHeatmap(months = 12) {
    return await this.request('GET', `/insights/heatmap?months=${months}`);
  }

  async getSummary() {
    return await this.request('GET', '/insights/summary');
  }

  async getRecommendations(category = null, priority = null) {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (priority) params.append('priority', priority);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return await this.request('GET', `/recommendations/${qs}`);
  }

  // Doctor Portal Endpoints
  async doctorLogin(email, password) {
    // Doctors login via the normal auth flow
    return await this.login(email, password);
  }

  async getPatients() {
    return await this.request('GET', '/doctor/patients');
  }

  async getPatientSummary(patientId) {
    return await this.request('GET', `/doctor/patients/${patientId}`);
  }

  async getRelevantRecords(patientId, complaint) {
    return await this.request('GET', `/doctor/patients/${patientId}/relevant?complaint=${encodeURIComponent(complaint)}`);
  }
}

const api = new GenHealthAPI(CONFIG.API_BASE);
window.api = api;
