/**
 * Thin fetch wrapper.
 *
 * Hand-written at M0. Once the requirement and evidence endpoints land in M1 this is
 * replaced by a client generated from the API's OpenAPI schema, so types stop being
 * maintained on both sides of the boundary.
 */

const API_BASE = '/api/v1';

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    fields?: { path: string; message: string }[];
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields?: { path: string; message: string }[];

  constructor(status: number, body: ApiErrorBody | null, fallback: string) {
    super(body?.error?.message ?? fallback);
    this.name = 'ApiError';
    this.status = status;
    this.code = body?.error?.code ?? 'unknown_error';
    this.fields = body?.error?.fields;
  }

  get isUnauthenticated(): boolean {
    return this.status === 401;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    // The session is an httpOnly cookie; it must ride along on every call.
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  });

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const payload: unknown = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new ApiError(response.status, payload as ApiErrorBody | null, response.statusText);
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
};

/* ─────────────────────────────────────────────────────────────────────── types */

export type Role = 'viewer' | 'auditor' | 'engineer' | 'owner';

export interface Permissions {
  can_write: boolean;
  can_manage_members: boolean;
  can_export: boolean;
}

export interface Organization {
  id: string;
  slug: string;
  name: string;
  merchant_level: string;
  saq_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  last_login_at: string | null;
}

export interface SessionResponse {
  user: User;
  organization: Organization;
  role: Role;
  permissions: Permissions;
}

export interface DeploymentStatus {
  bootstrapped: boolean;
  deployment_mode: 'single_tenant' | 'saas';
  signup_enabled: boolean;
}

export interface AuditEntry {
  id: string;
  seq: number;
  at: string;
  actor_label: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown>;
  hash: string;
  prev_hash: string;
}

export interface AuditChainStatus {
  ok: boolean;
  entries_checked: number;
  first_bad_seq: number | null;
  reason: string | null;
  summary: string;
}

export const endpoints = {
  deployment: () => api.get<DeploymentStatus>('/auth/deployment'),
  session: () => api.get<SessionResponse>('/auth/session'),
  login: (body: { email: string; password: string; org_slug?: string }) =>
    api.post<SessionResponse>('/auth/login', body),
  bootstrap: (body: {
    org_name: string;
    full_name: string;
    email: string;
    password: string;
  }) => api.post<SessionResponse>('/auth/bootstrap', body),
  logout: () => api.post<void>('/auth/logout'),
  auditEntries: (limit = 50) => api.get<AuditEntry[]>(`/audit/entries?limit=${limit}`),
  auditChain: () => api.get<AuditChainStatus>('/audit/chain'),
};
