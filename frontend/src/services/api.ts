import { 
  type AnalysisResponse, 
  type DashboardStats, 
  type HistoryItem, 
  type ComplianceRule, 
  type AuthUser, 
  type RegisterUserPayload,
  type RegisterMerchantPayload,
  type OfficerAccessRequestPayload,
  type OfficerAccessRequestItem,
  type OfficerAccessRequestPublicStatus,
  type AdminApproveOfficerResponse,
  type TrendPoint, 
  type StatusBreakdown, 
  type PenaltyEstimate, 
  type ShowCauseNotice, 
  type ProductInfo, 
  type ComplianceResult, 
  type RuleTestRequest, 
  type RuleTestResponse, 
  type RuleConflictItem, 
  type ScoringConfiguration, 
  type ScoreHistoryEntry, 
  type ProductRiskHistory, 
  type BatchRiskDistribution,
  type PreprintUploadResponse,
  type PreprintAnalysisResponse,
  type PreprintApprovalRequest,
  type ArtworkDocument,
  type VersionComparisonRequest,
  type VersionComparisonResult,
  type VersionTimelineEvent,
  type OfficerDashboardSummary,
  type ReviewItem,
  type ReviewDetailResponse,
  type AIvsHumanComparison,
  type ReviewHistoryEvent,
  type Product,
  type ProductCreateInput,
  type ProductUpdateInput,
  type ProductListResponse,
  type ProductHistoryItem,
  type ProductArtworkSummary,
  type ProductComplianceSummary,
  type MerchantDashboardStats,
  type EnforcementDashboardMetrics,
  type EnforcementCaseSummary,
  type EnforcementCaseDetail,
  type PenaltyCalculationRecord,
  type EnforcementNotice
} from '../types';

const API_HOST = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const BASE_URL = API_HOST ? `${API_HOST}/api` : '/api';

const TOKEN_KEY = 'metrcheck-token';

export const tokenStore = {
  get: (): string | null => {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set: (token: string) => {
    try { localStorage.setItem(TOKEN_KEY, token); } catch { /* ignore */ }
  },
  clear: () => {
    try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
  },
};

function authHeaders(): Record<string, string> {
  const token = tokenStore.get();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> | undefined),
    ...authHeaders(),
  };
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    let errorMessage = '';

    if (errorBody?.detail) {
      if (typeof errorBody.detail === 'string') {
        if (errorBody.detail === 'Not Found' && response.status === 404) {
          errorMessage = 'The requested service endpoint was not found. Please verify the backend server is running and up to date.';
        } else {
          errorMessage = errorBody.detail;
        }
      } else if (Array.isArray(errorBody.detail)) {
        errorMessage = errorBody.detail
          .map((err: any) => (err?.loc ? `${err.loc.slice(-1)}: ${err.msg}` : err.msg || JSON.stringify(err)))
          .join(', ');
      } else if (typeof errorBody.detail === 'object') {
        errorMessage = JSON.stringify(errorBody.detail);
      }
    } else if (errorBody?.message && typeof errorBody.message === 'string') {
      errorMessage = errorBody.message;
    }

    if (!errorMessage) {
      if (response.status === 404) {
        errorMessage = 'Endpoint not found (404). Please ensure the backend server is running.';
      } else if (response.status === 500) {
        errorMessage = 'Internal server error (500). Please try again later.';
      } else if (response.status === 504) {
        errorMessage = 'The cloud instance was waking up or processing dense package scans. The server is warm now—please click Retry!';
      } else if (response.status === 502 || response.status === 503) {
        errorMessage = 'The server is currently waking up from standby. Please wait a moment and click Retry.';
      } else {
        errorMessage = `API error: ${response.status} ${response.statusText}`.trim();
      }
    }

    if (response.status === 401) {
      if (!url.includes('/auth/login')) {
        tokenStore.clear();
      }
      throw new Error(errorMessage || 'Authentication required. Please log in again.');
    }

    throw new Error(errorMessage);
  }
  return response.json();
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────
  login: (username: string, password: string): Promise<{ token: string; user: AuthUser }> =>
    fetchJSON<{ token: string; user: AuthUser }>(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }),

  forgotPassword: (identifier: string): Promise<{ message: string }> =>
    fetchJSON<{ message: string }>(`${BASE_URL}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier }),
    }),


  verifyResetToken: (token: string): Promise<{ valid: boolean; username?: string }> =>
    fetchJSON<{ valid: boolean; username?: string }>(`${BASE_URL}/auth/verify-reset-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    }),

  resetPassword: (token: string, new_password: string): Promise<{ message: string }> =>
    fetchJSON<{ message: string }>(`${BASE_URL}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password }),
    }),

  verifyInvitation: (token: string): Promise<import('../types').InvitationVerification> =>
    fetchJSON<import('../types').InvitationVerification>(`${BASE_URL}/auth/verify-invitation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    }),

  activateAccount: (token: string, password: string): Promise<{ message: string; username: string }> =>
    fetchJSON<{ message: string; username: string }>(`${BASE_URL}/auth/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, password }),
    }),

  registerUser: (body: RegisterUserPayload): Promise<{ token: string; user: AuthUser }> =>
    fetchJSON<{ token: string; user: AuthUser }>(`${BASE_URL}/auth/register-user`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  registerMerchant: (body: RegisterMerchantPayload): Promise<{ token: string; user: AuthUser }> =>
    fetchJSON<{ token: string; user: AuthUser }>(`${BASE_URL}/auth/register-merchant`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  register: (body: { username: string; email: string; password: string; full_name?: string; role?: string }): Promise<{ token: string; user: AuthUser }> =>
    fetchJSON<{ token: string; user: AuthUser }>(`${BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  getMe: (): Promise<AuthUser> => fetchJSON<AuthUser>(`${BASE_URL}/auth/me`),

  updateMyEmail: (email: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/me/email`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    }),

  // ── Administration API (/api/admin) ──────────────────────────────────
  adminGetUsers: (): Promise<AuthUser[]> => fetchJSON<AuthUser[]>(`${BASE_URL}/admin/users`),

  adminProvisionUser: (body: {
    full_name?: string;
    username: string;
    email: string;
    role: string;
    jurisdiction?: string;
  }): Promise<{ message: string; user: AuthUser; dev_invitation_token?: string }> =>
    fetchJSON<{ message: string; user: AuthUser; dev_invitation_token?: string }>(`${BASE_URL}/admin/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  adminResendInvitation: (username: string): Promise<{ message: string; username: string; dev_invitation_token?: string }> =>
    fetchJSON<{ message: string; username: string; dev_invitation_token?: string }>(
      `${BASE_URL}/admin/users/${encodeURIComponent(username)}/resend-invitation`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }
    ),

  adminSuspendUser: (username: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/suspend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),

  adminReactivateUser: (username: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/reactivate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),

  adminChangeRole: (username: string, role: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/change-role`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    }),

  adminDeleteUser: async (username: string): Promise<void> => {
    const headers: Record<string, string> = {
      ...authHeaders(),
    };
    const response = await fetch(`${BASE_URL}/admin/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers,
    });
    if (response.status === 401) {
      tokenStore.clear();
      throw new Error('Authentication required. Please log in again.');
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail || `API error: ${response.status} ${response.statusText}`);
    }
  },

  adminGetAuditLogs: (limit = 50): Promise<import('../types').AccountAuditLog[]> =>
    fetchJSON<import('../types').AccountAuditLog[]>(`${BASE_URL}/admin/audit-logs?limit=${limit}`),

  // ── Officer Access Requests ───────────────────────────────────────────
  submitOfficerAccessRequest: (payload: OfficerAccessRequestPayload): Promise<OfficerAccessRequestItem> =>
    fetchJSON<OfficerAccessRequestItem>(`${BASE_URL}/officer-access/requests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  getOfficerAccessRequestStatus: (requestId: string): Promise<OfficerAccessRequestPublicStatus> =>
    fetchJSON<OfficerAccessRequestPublicStatus>(`${BASE_URL}/officer-access/requests/${encodeURIComponent(requestId)}`),

  // ── Admin Officer Requests Management ──────────────────────────────────
  adminGetOfficerRequests: (status?: string, search?: string): Promise<OfficerAccessRequestItem[]> => {
    const params = new URLSearchParams();
    if (status && status !== 'ALL') params.append('status', status);
    if (search) params.append('search', search);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return fetchJSON<OfficerAccessRequestItem[]>(`${BASE_URL}/admin/officer-requests${qs}`);
  },

  adminGetOfficerRequestDetail: (requestId: string): Promise<OfficerAccessRequestItem> =>
    fetchJSON<OfficerAccessRequestItem>(`${BASE_URL}/admin/officer-requests/${encodeURIComponent(requestId)}`),

  adminApproveOfficerRequest: (requestId: string): Promise<AdminApproveOfficerResponse> =>
    fetchJSON<AdminApproveOfficerResponse>(`${BASE_URL}/admin/officer-requests/${encodeURIComponent(requestId)}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),

  adminRejectOfficerRequest: (requestId: string, rejectionReason: string): Promise<OfficerAccessRequestItem> =>
    fetchJSON<OfficerAccessRequestItem>(`${BASE_URL}/admin/officer-requests/${encodeURIComponent(requestId)}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rejection_reason: rejectionReason }),
    }),

  // Legacy User APIs
  getUsers: (): Promise<AuthUser[]> => fetchJSON<AuthUser[]>(`${BASE_URL}/auth/users`),

  createUser: (body: { username: string; email?: string; password: string; full_name?: string; jurisdiction?: string; role?: string }): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateUser: (
    username: string,
    updates: { full_name?: string; jurisdiction?: string; email?: string; role?: string; new_password?: string }
  ): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/users/${encodeURIComponent(username)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    }),

  deleteUser: async (username: string): Promise<void> => {
    const headers: Record<string, string> = {
      ...authHeaders(),
    };
    const response = await fetch(`${BASE_URL}/auth/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers,
    });
    if (response.status === 401) {
      tokenStore.clear();
      throw new Error('Authentication required. Please log in again.');
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail || `API error: ${response.status} ${response.statusText}`);
    }
  },

  // ── Analyses ──────────────────────────────────────────────────────────
  analyzeProduct: async (file: File, productId?: string): Promise<AnalysisResponse> => {
    const formData = new FormData();
    formData.append('files', file);
    formData.append('labels', JSON.stringify(['Front']));
    if (productId) {
      formData.append('product_id', productId);
    }
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
    });
  },

  analyzeProducts: async (items: { file: File; label: string }[], productId?: string): Promise<AnalysisResponse> => {
    const formData = new FormData();
    const labels: string[] = [];
    items.forEach((item) => {
      formData.append('files', item.file);
      labels.push(item.label || 'Front');
    });
    formData.append('labels', JSON.stringify(labels));
    if (productId) {
      formData.append('product_id', productId);
    }
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
    });
  },

  analyzeText: (text: string, productId?: string): Promise<AnalysisResponse> =>
    fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, product_id: productId || null }),
    }),

  analyzeManual: (payload: import('../types').ManualProductCheckPayload): Promise<AnalysisResponse> =>
    fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  getDashboardStats: (): Promise<DashboardStats> => {
    return fetchJSON<DashboardStats>(`${BASE_URL}/stats`);
  },

  getTrends: (days = 14): Promise<TrendPoint[]> => {
    return fetchJSON<TrendPoint[]>(`${BASE_URL}/stats/trends?days=${days}`);
  },

  getStatusBreakdown: (): Promise<StatusBreakdown[]> => {
    return fetchJSON<StatusBreakdown[]>(`${BASE_URL}/stats/by-status`);
  },

  getHistory: (): Promise<HistoryItem[]> => {
    return fetchJSON<HistoryItem[]>(`${BASE_URL}/history`);
  },

  searchHistory: (q: string, status = 'ALL', limit = 50): Promise<{ items: HistoryItem[]; total: number }> => {
    const params = new URLSearchParams({ q, status, limit: String(limit) });
    return fetchJSON<{ items: HistoryItem[]; total: number }>(`${BASE_URL}/history/search?${params}`);
  },

  getAnalysis: (id: string): Promise<AnalysisResponse> => {
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/history/${id}`);
  },

  deleteAnalysis: (id: string): Promise<{ message: string; id: string }> => {
    return fetchJSON<{ message: string; id: string }>(`${BASE_URL}/history/${id}`, {
      method: 'DELETE',
    });
  },

  clearHistory: (): Promise<{ message: string; deleted_count: number }> => {
    return fetchJSON<{ message: string; deleted_count: number }>(`${BASE_URL}/history`, {
      method: 'DELETE',
    });
  },

  // ── Enforcement (officer/admin only) ──────────────────────────────────
  estimatePenalty: (analysisId: string): Promise<PenaltyEstimate> => {
    return fetchJSON<PenaltyEstimate>(`${BASE_URL}/enforcement/penalty`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId }),
    });
  },

  showCauseNotice: (analysisId: string): Promise<ShowCauseNotice> => {
    return fetchJSON<ShowCauseNotice>(`${BASE_URL}/enforcement/notice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId }),
    });
  },

  // ── Demo / reference / misc ───────────────────────────────────────────
  getDemoCases: (): Promise<import('../types').DemoCaseMeta[]> => {
    return fetchJSON<import('../types').DemoCaseMeta[]>(`${BASE_URL}/demo/cases`);
  },

  getDemoCase: (caseNum: number | string): Promise<AnalysisResponse> => {
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/demo/${caseNum}`);
  },

  getComplianceRules: (params?: { category?: string; domain?: string; version?: string }): Promise<ComplianceRule[]> => {
    const query = new URLSearchParams();
    if (params?.category) query.append('category', params.category);
    if (params?.domain) query.append('domain', params.domain);
    if (params?.version) query.append('version', params.version);
    const qs = query.toString();
    return fetchJSON<ComplianceRule[]>(`${BASE_URL}/compliance/rules${qs ? `?${qs}` : ''}`);
  },

  getComplianceRuleDetail: (ruleId: string): Promise<ComplianceRule> => {
    return fetchJSON<ComplianceRule>(`${BASE_URL}/compliance/rules/${encodeURIComponent(ruleId)}`);
  },

  testComplianceRule: (req: RuleTestRequest): Promise<RuleTestResponse> => {
    return fetchJSON<RuleTestResponse>(`${BASE_URL}/compliance/test-rule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
  },

  getAnalysisConflicts: (analysisId: string): Promise<{ analysis_id: string; conflicts: RuleConflictItem[] }> => {
    return fetchJSON<{ analysis_id: string; conflicts: RuleConflictItem[] }>(`${BASE_URL}/compliance/conflicts/${encodeURIComponent(analysisId)}`);
  },

  getHealth: (): Promise<any> => {
    return fetchJSON<any>(`${BASE_URL}/health`);
  },
  requestDownloadTicket: async (resourceType: string, resourceId: string): Promise<string> => {
    const res = await fetchJSON<{ ticket: string }>(`${BASE_URL}/auth/download-ticket`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resource_type: resourceType, resource_id: resourceId }),
    });
    return res.ticket;
  },
  getReportUrl: (id: string, lang?: string, ticket?: string): string => {
    const params = new URLSearchParams();
    if (lang && lang !== 'en') {
      params.append('lang', lang);
    }
    if (ticket) {
      params.append('ticket', ticket);
    }
    const qs = params.toString();
    return `${BASE_URL}/report/${encodeURIComponent(id)}${qs ? `?${qs}` : ''}`;
  },
  getCsvReportUrl: (id: string, ticket?: string): string => {
    return `${BASE_URL}/report/${encodeURIComponent(id)}/csv${ticket ? `?ticket=${encodeURIComponent(ticket)}` : ''}`;
  },
  getXlsxReportUrl: (id: string, ticket?: string): string => {
    return `${BASE_URL}/report/${encodeURIComponent(id)}/xlsx${ticket ? `?ticket=${encodeURIComponent(ticket)}` : ''}`;
  },
  getJsonReportUrl: (id: string, ticket?: string): string => {
    return `${BASE_URL}/report/${encodeURIComponent(id)}/json${ticket ? `?ticket=${encodeURIComponent(ticket)}` : ''}`;
  },
  downloadReportFile: async (id: string, format: 'pdf' | 'csv' | 'xlsx' | 'json', lang?: string): Promise<void> => {
    let url = '';
    let ext = format;
    if (format === 'pdf') {
      url = api.getReportUrl(id, lang);
    } else if (format === 'csv') {
      url = api.getCsvReportUrl(id);
    } else if (format === 'xlsx') {
      url = api.getXlsxReportUrl(id);
    } else if (format === 'json') {
      url = api.getJsonReportUrl(id);
    }

    const token = tokenStore.get();
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch(url, { headers });
      if (res.ok) {
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `metrcheck-compliance-report-${id}.${ext}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
        return;
      }
    } catch {
      // Fallback with download ticket
    }

    try {
      const ticket = await api.requestDownloadTicket('report', id);
      const ticketUrl = url.includes('?') ? `${url}&ticket=${encodeURIComponent(ticket)}` : `${url}?ticket=${encodeURIComponent(ticket)}`;
      window.open(ticketUrl, '_blank');
    } catch {
      window.open(url, '_blank');
    }
  },
  getAssetUrl: (url: string, ticket?: string): string => {
    if (!url) return '';
    if (url.startsWith('data:')) return url;
    let cleanUrl = url.startsWith('/uploads/') ? url.replace('/uploads/', '/api/images/') : url;
    let fullUrl = (cleanUrl.startsWith('http://') || cleanUrl.startsWith('https://'))
      ? cleanUrl
      : (API_HOST ? `${API_HOST}${cleanUrl}` : cleanUrl);
    if (ticket) {
      const sep = fullUrl.includes('?') ? '&' : '?';
      return `${fullUrl}${sep}ticket=${encodeURIComponent(ticket)}`;
    }
    return fullUrl;
  },

  fetchImageBlobUrl: async (url: string, timeoutMs: number = 8000): Promise<string> => {
    if (!url) return '';
    if (url.startsWith('data:') || url.startsWith('blob:')) return url;
    let cleanUrl = url.startsWith('/uploads/') ? url.replace('/uploads/', '/api/images/') : url;
    let fullUrl = (cleanUrl.startsWith('http://') || cleanUrl.startsWith('https://'))
      ? cleanUrl
      : (API_HOST ? `${API_HOST}${cleanUrl}` : cleanUrl);
    const token = tokenStore.get();
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    
    const controller = new AbortController();
    const timerId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(fullUrl, { headers, signal: controller.signal });
      if (!res.ok) {
        throw new Error(`Failed to fetch image blob: ${res.status} ${res.statusText}`);
      }
      const blob = await res.blob();
      return URL.createObjectURL(blob);
    } finally {
      clearTimeout(timerId);
    }
  },
  extractText: (text: string): Promise<ProductInfo> =>
    fetchJSON<ProductInfo>(`${BASE_URL}/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),

  checkCompliance: (info: ProductInfo): Promise<ComplianceResult> =>
    fetchJSON<ComplianceResult>(`${BASE_URL}/compliance/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(info),
    }),

  // ── Scoring & Risk (Section 7) ──────────────────────────────────────────
  getScoringConfig: (): Promise<ScoringConfiguration> =>
    fetchJSON<ScoringConfiguration>(`${BASE_URL}/scoring/config`),

  updateScoringConfig: (config: ScoringConfiguration): Promise<ScoringConfiguration> =>
    fetchJSON<ScoringConfiguration>(`${BASE_URL}/scoring/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }),

  getScoreHistory: (analysisId: string): Promise<ScoreHistoryEntry> =>
    fetchJSON<ScoreHistoryEntry>(`${BASE_URL}/scoring/history/${encodeURIComponent(analysisId)}`),

  getProductRiskHistory: (productName: string): Promise<ProductRiskHistory> =>
    fetchJSON<ProductRiskHistory>(`${BASE_URL}/scoring/product/${encodeURIComponent(productName)}/history`),

  getBatchRiskDistribution: (ownerUserId?: string): Promise<BatchRiskDistribution> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}` : '';
    return fetchJSON<BatchRiskDistribution>(`${BASE_URL}/scoring/batch-distribution${qs}`);
  },

  // ── Pre-Print Packaging Compliance (Section 8) ──────────────────────────
  uploadArtwork: async (file: File, parentArtworkId?: string, iterationNumber = 1, productId?: string): Promise<PreprintUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (parentArtworkId) {
      formData.append('parent_artwork_id', parentArtworkId);
    }
    formData.append('iteration_number', String(iterationNumber));
    if (productId) {
      formData.append('product_id', productId);
    }
    return fetchJSON<PreprintUploadResponse>(`${BASE_URL}/preprint/upload`, {
      method: 'POST',
      body: formData,
    });
  },

  analyzeArtwork: (artworkId: string, productName?: string, category?: string): Promise<PreprintAnalysisResponse> => {
    const params = new URLSearchParams();
    if (productName) params.append('product_name', productName);
    if (category) params.append('category', category);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return fetchJSON<PreprintAnalysisResponse>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}/analyze${qs}`, {
      method: 'POST',
    });
  },

  getArtwork: (artworkId: string): Promise<ArtworkDocument> =>
    fetchJSON<ArtworkDocument>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}`),

  uploadArtworkCorrection: async (artworkId: string, file: File): Promise<PreprintAnalysisResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    return fetchJSON<PreprintAnalysisResponse>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}/correction-upload`, {
      method: 'POST',
      body: formData,
    });
  },

  submitArtworkApproval: (artworkId: string, req: PreprintApprovalRequest): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}/approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),

  listArtworks: (ownerUserId?: string): Promise<{ artworks: ArtworkDocument[]; total: number }> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}` : '';
    return fetchJSON<{ artworks: ArtworkDocument[]; total: number }>(`${BASE_URL}/preprint${qs}`);
  },

  deleteArtwork: (artworkId: string): Promise<{ success: boolean; message: string }> =>
    fetchJSON<{ success: boolean; message: string }>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}`, {
      method: 'DELETE',
    }),

  // ── Section 9 Version Comparison ─────────────────────────────────────────
  compareVersions: (req: VersionComparisonRequest): Promise<VersionComparisonResult> =>
    fetchJSON<VersionComparisonResult>(`${BASE_URL}/versions/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),

  getComparison: (comparisonId: string): Promise<VersionComparisonResult> =>
    fetchJSON<VersionComparisonResult>(`${BASE_URL}/versions/comparisons/${encodeURIComponent(comparisonId)}`),

  listComparisons: (ownerUserId?: string, limit = 50): Promise<{ comparisons: VersionComparisonResult[]; total: number }> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}&limit=${limit}` : `?limit=${limit}`;
    return fetchJSON<{ comparisons: VersionComparisonResult[]; total: number }>(`${BASE_URL}/versions/comparisons${qs}`);
  },

  getVersionTimeline: (entityId: string): Promise<{ entity_id: string; events: VersionTimelineEvent[]; total: number }> =>
    fetchJSON<{ entity_id: string; events: VersionTimelineEvent[]; total: number }>(`${BASE_URL}/versions/timeline/${encodeURIComponent(entityId)}`),

  getVersionTargets: (ownerUserId?: string): Promise<{ targets: any[]; total: number }> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}` : '';
    return fetchJSON<{ targets: any[]; total: number }>(`${BASE_URL}/versions/targets${qs}`);
  },

  // ── Section 10 Human Verification / Officer Workflow ─────────────────────
  getReviewDashboard: (): Promise<OfficerDashboardSummary> =>
    fetchJSON<OfficerDashboardSummary>(`${BASE_URL}/reviews/dashboard`),

  getReviewQueue: (status?: string, assignedOfficer?: string, riskLevel?: string, limit = 100): Promise<ReviewItem[]> => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (assignedOfficer) params.append('assigned_officer', assignedOfficer);
    if (riskLevel) params.append('risk_level', riskLevel);
    params.append('limit', String(limit));
    return fetchJSON<ReviewItem[]>(`${BASE_URL}/reviews/queue?${params.toString()}`);
  },

  getAvailableOfficers: (): Promise<{ officers: Array<{ username: string; full_name: string; role: string; status: string }>; total: number }> =>
    fetchJSON<{ officers: Array<{ username: string; full_name: string; role: string; status: string }>; total: number }>(`${BASE_URL}/reviews/officers`),

  getReviewDetails: (reviewId: string): Promise<ReviewDetailResponse> =>
    fetchJSON<ReviewDetailResponse>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}`),

  assignReview: (reviewId: string, assignedOfficer: string, comments?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assigned_officer: assignedOfficer, comments }),
    }),

  acceptReview: (reviewId: string, comments?: string, finalStatus?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/accept`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comments, final_status: finalStatus }),
    }),

  rejectReview: (reviewId: string, rejectionReason: string, comments: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rejection_reason: rejectionReason, comments }),
    }),

  correctReviewField: (
    reviewId: string, 
    fieldName: string, 
    fieldLabel: string, 
    correctedValue: string, 
    reason?: string, 
    evidenceId?: string
  ): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/correct-field`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        field_name: fieldName,
        field_label: fieldLabel,
        corrected_value: correctedValue,
        reason,
        evidence_id: evidenceId
      }),
    }),

  addReviewEvidence: (
    reviewId: string,
    data: {
      image_index: number;
      image_label: string;
      text: string;
      bbox?: number[];
      linked_rule_id: string;
      linked_field: string;
      comments?: string;
    }
  ): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/evidence/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  removeReviewEvidence: (reviewId: string, evidenceId: string, reason: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/evidence/remove`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ evidence_id: evidenceId, reason }),
    }),

  addReviewComment: (reviewId: string, text: string, commentType = 'GENERAL'): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/comment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, comment_type: commentType }),
    }),

  escalateReview: (reviewId: string, escalationReason: string, comments?: string, escalationTarget?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/escalate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        escalation_reason: escalationReason,
        comments,
        escalation_target: escalationTarget
      }),
    }),

  reopenReview: (reviewId: string, reopenReason: string, comments?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/reopen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reopen_reason: reopenReason, comments }),
    }),

  getAIvsHumanDiff: (reviewId: string): Promise<AIvsHumanComparison> =>
    fetchJSON<AIvsHumanComparison>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/ai-vs-human`),

  getReviewHistory: (reviewId: string): Promise<{ review_id: string; history: ReviewHistoryEvent[]; total: number }> =>
    fetchJSON<{ review_id: string; history: ReviewHistoryEvent[]; total: number }>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/history`),

  // ── Merchant Product Catalog & Workspace ────────────────────────────────
  createProduct: (data: ProductCreateInput): Promise<Product> =>
    fetchJSON<Product>(`${BASE_URL}/products`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  getProducts: (params?: { q?: string; status?: string; category?: string; limit?: number; offset?: number }): Promise<ProductListResponse> => {
    const query = new URLSearchParams();
    if (params?.q) query.append('q', params.q);
    if (params?.status) query.append('status', params.status);
    if (params?.category) query.append('category', params.category);
    if (params?.limit !== undefined) query.append('limit', String(params.limit));
    if (params?.offset !== undefined) query.append('offset', String(params.offset));
    const qs = query.toString() ? `?${query.toString()}` : '';
    return fetchJSON<ProductListResponse>(`${BASE_URL}/products${qs}`);
  },

  getProductStats: (): Promise<MerchantDashboardStats> =>
    fetchJSON<MerchantDashboardStats>(`${BASE_URL}/products/stats`),

  getProduct: (id: string): Promise<Product> =>
    fetchJSON<Product>(`${BASE_URL}/products/${encodeURIComponent(id)}`),

  updateProduct: (id: string, data: ProductUpdateInput): Promise<Product> =>
    fetchJSON<Product>(`${BASE_URL}/products/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  archiveProduct: (id: string): Promise<{ message: string; id: string }> =>
    fetchJSON<{ message: string; id: string }>(`${BASE_URL}/products/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),

  deleteProduct: (id: string): Promise<{ message: string; id: string }> =>
    fetchJSON<{ message: string; id: string }>(`${BASE_URL}/products/${encodeURIComponent(id)}?hard_delete=true`, {
      method: 'DELETE',
    }),

  getProductHistory: (id: string): Promise<{ product_id: string; analyses: ProductHistoryItem[]; total: number }> =>
    fetchJSON<{ product_id: string; analyses: ProductHistoryItem[]; total: number }>(`${BASE_URL}/products/${encodeURIComponent(id)}/history`),

  getProductArtworks: (id: string): Promise<{ product_id: string; artworks: ProductArtworkSummary[]; total: number }> =>
    fetchJSON<{ product_id: string; artworks: ProductArtworkSummary[]; total: number }>(`${BASE_URL}/products/${encodeURIComponent(id)}/artworks`),

  getProductSummary: (id: string): Promise<ProductComplianceSummary> =>
    fetchJSON<ProductComplianceSummary>(`${BASE_URL}/products/${encodeURIComponent(id)}/summary`),

  // ── Phase 4B: Enforcement Case Management & Statutory Notices ─────────────
  getEnforcementDashboard: (): Promise<EnforcementDashboardMetrics> =>
    fetchJSON<EnforcementDashboardMetrics>(`${BASE_URL}/enforcement/dashboard`),

  getAvailableEnforcementOfficers: (): Promise<{ officers: Array<{ username: string; full_name: string; role: string; status: string }>; total: number }> =>
    fetchJSON<{ officers: Array<{ username: string; full_name: string; role: string; status: string }>; total: number }>(`${BASE_URL}/enforcement/officers`),

  listEnforcementCases: (params?: {
    status?: string;
    severity?: string;
    assigned_officer?: string;
    jurisdiction_state?: string;
    jurisdiction_district?: string;
    merchant_organization_id?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<{ cases: EnforcementCaseSummary[]; total: number; page: number; page_size: number }> => {
    const q = new URLSearchParams();
    if (params?.status && params.status !== 'ALL') q.append('status', params.status);
    if (params?.severity && params.severity !== 'ALL') q.append('severity', params.severity);
    if (params?.assigned_officer && params.assigned_officer !== 'ALL') q.append('assigned_officer', params.assigned_officer);
    if (params?.jurisdiction_state) q.append('jurisdiction_state', params.jurisdiction_state);
    if (params?.jurisdiction_district) q.append('jurisdiction_district', params.jurisdiction_district);
    if (params?.merchant_organization_id) q.append('merchant_organization_id', params.merchant_organization_id);
    if (params?.search) q.append('search', params.search);
    if (params?.page) q.append('page', String(params.page));
    if (params?.page_size) q.append('page_size', String(params.page_size));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return fetchJSON<{ cases: EnforcementCaseSummary[]; total: number; page: number; page_size: number }>(`${BASE_URL}/enforcement/cases${qs}`);
  },

  getEnforcementCase: (caseIdOrRef: string): Promise<EnforcementCaseDetail> =>
    fetchJSON<EnforcementCaseDetail>(`${BASE_URL}/enforcement/cases/${encodeURIComponent(caseIdOrRef)}`),

  createEnforcementCase: (data: {
    analysis_id: string;
    review_id?: string;
    product_id?: string;
    merchant_organization_id?: string;
    violation_summary?: string;
    severity?: string;
    initial_notes?: string;
  }): Promise<EnforcementCaseDetail> =>
    fetchJSON<EnforcementCaseDetail>(`${BASE_URL}/enforcement/cases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  assignEnforcementCase: (caseIdOrRef: string, assignedOfficer: string, comments?: string): Promise<EnforcementCaseDetail> =>
    fetchJSON<EnforcementCaseDetail>(`${BASE_URL}/enforcement/cases/${encodeURIComponent(caseIdOrRef)}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assigned_officer: assignedOfficer, comments }),
    }),

  transitionEnforcementCase: (caseIdOrRef: string, toStatus: string, reason: string, comments?: string): Promise<EnforcementCaseDetail> =>
    fetchJSON<EnforcementCaseDetail>(`${BASE_URL}/enforcement/cases/${encodeURIComponent(caseIdOrRef)}/transition`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to_status: toStatus, reason, comments }),
    }),

  calculateCasePenalty: (caseIdOrRef: string, repeatOffence = false, priorNotices = 0, reason?: string): Promise<PenaltyCalculationRecord> =>
    fetchJSON<PenaltyCalculationRecord>(`${BASE_URL}/enforcement/cases/${encodeURIComponent(caseIdOrRef)}/calculate-penalty`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repeat_offence: repeatOffence, prior_notices: priorNotices, reason }),
    }),

  issueCaseNotice: (caseIdOrRef: string, req: {
    notice_type?: string;
    subject?: string;
    officer_name?: string;
    officer_designation?: string;
    jurisdiction?: string;
    deadline_days?: number;
    recipient_name?: string;
    recipient_organization_id?: string;
    custom_content?: string;
  }): Promise<EnforcementNotice> =>
    fetchJSON<EnforcementNotice>(`${BASE_URL}/enforcement/cases/${encodeURIComponent(caseIdOrRef)}/notices`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),

  closeEnforcementCase: (caseIdOrRef: string, closureReason: string, resolutionType = 'COMPOUNDED', comments?: string): Promise<EnforcementCaseDetail> =>
    fetchJSON<EnforcementCaseDetail>(`${BASE_URL}/enforcement/cases/${encodeURIComponent(caseIdOrRef)}/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ closure_reason: closureReason, resolution_type: resolutionType, comments }),
    }),

  reopenEnforcementCase: (caseIdOrRef: string, reopenReason: string, comments?: string): Promise<EnforcementCaseDetail> =>
    fetchJSON<EnforcementCaseDetail>(`${BASE_URL}/enforcement/cases/${encodeURIComponent(caseIdOrRef)}/reopen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reopen_reason: reopenReason, comments }),
    }),
};

export default api;