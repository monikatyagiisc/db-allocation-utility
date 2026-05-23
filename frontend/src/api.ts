import { log } from './logger';

const API_BASE = '/api';

export type User = {
  id: number;
  email: string;
  full_name: string | null;
  created_at: string;
};

export type DatabaseRecord = {
  id: number;
  serial_number: number | null;
  database_type: string | null;
  database_name: string;
  cics_transactions: number | null;
  prod_mirror: string | null;
  release: string | null;
  lifecycle: string | null;
  status: string | null;
  assignee: string | null;
  team: string | null;
  project: string | null;
  start_date: string | null;
  end_date: string | null;
  can_be_released: string | null;
  jira_key: string | null;
  comments: string | null;
  created_at: string;
  updated_at: string | null;
};

export type TypeBreakdown = {
  database_type: string;
  count: number;
  prod_mirror_count: number;
  expiring_this_month: number;
  expiring_next_month: number;
  blocked_count: number;
  can_be_released_count: number;
};

export type KPIs = {
  total_databases: number;
  expiring_this_month: number;
  expiring_next_month: number;
  prod_mirror_count: number;
  can_be_released_count: number;
  blocked_count: number;
  by_type: TypeBreakdown[];
};

function getToken(): string | null {
  return localStorage.getItem('token');
}

function parseErrorDetail(err: unknown): string {
  if (typeof err === 'string') return err;
  if (err && typeof err === 'object' && 'detail' in err) {
    const detail = (err as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((d) => JSON.stringify(d)).join(', ');
  }
  return 'Request failed';
}

async function handleResponse<T>(res: Response, method: string, path: string): Promise<T> {
  const requestId = res.headers.get('x-request-id');
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = parseErrorDetail(err);
    const rid = (err as { request_id?: string }).request_id || requestId;
    log.error(`${method} ${path} failed`, {
      status: res.status,
      detail,
      request_id: rid,
    });
    if (rid) {
      throw new Error(`${detail} (request_id: ${rid} — search [BE] logs for this id)`);
    }
    throw new Error(detail);
  }
  log.info(`${method} ${path} ok`, { status: res.status, request_id: requestId });
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = options.method || 'GET';
  log.debug(`${method} ${path}`);
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  return handleResponse<T>(res, method, path);
}

export async function login(email: string, password: string) {
  log.info('POST /auth/login', { email });
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  return handleResponse<{ access_token: string }>(res, 'POST', '/auth/login');
}

export async function register(email: string, password: string, fullName?: string) {
  log.info('POST /auth/register', { email, full_name: fullName || null });
  return request<User>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name: fullName || null }),
  });
}

export async function getMe() {
  return request<User>('/auth/me');
}

export async function getKPIs() {
  return request<KPIs>('/databases/kpis');
}

export type KpiCategory =
  | 'expiring_this_month'
  | 'expiring_next_month'
  | 'prod_mirror'
  | 'can_be_released'
  | 'blocked'
  | 'total';

export type KpiListResponse = {
  category: string;
  title: string;
  count: number;
  records: DatabaseRecord[];
};

export async function getKpiList(category: KpiCategory, databaseType?: string) {
  const params = new URLSearchParams({ category });
  if (databaseType) params.set('database_type', databaseType);
  return request<KpiListResponse>(`/databases/kpi-list?${params.toString()}`);
}

export type SortOrder = 'asc' | 'desc';

export type ExpiryFilter = '' | 'expiring_this_month' | 'expiring_next_month';

export type DatabaseSortField =
  | 'serial_number'
  | 'database_type'
  | 'database_name'
  | 'cics_transactions'
  | 'prod_mirror'
  | 'release'
  | 'lifecycle'
  | 'status'
  | 'assignee'
  | 'team'
  | 'project'
  | 'start_date'
  | 'end_date'
  | 'can_be_released'
  | 'jira_key'
  | 'comments';

export async function listDatabases(
  search?: string,
  sortBy?: DatabaseSortField,
  sortOrder: SortOrder = 'asc',
  databaseType?: string,
  expiryFilter?: ExpiryFilter,
) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (databaseType) params.set('database_type', databaseType);
  if (expiryFilter) params.set('expiry_filter', expiryFilter);
  if (sortBy) {
    params.set('sort_by', sortBy);
    params.set('sort_order', sortOrder);
  }
  const q = params.toString() ? `?${params.toString()}` : '';
  return request<DatabaseRecord[]>(`/databases${q}`);
}

export async function updateDatabase(id: number, data: Partial<DatabaseRecord>) {
  return request<DatabaseRecord>(`/databases/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteDatabase(id: number) {
  return request<void>(`/databases/${id}`, { method: 'DELETE' });
}

export async function clearAllDatabases() {
  log.info('DELETE /databases/clear/all');
  return request<{ deleted: number; message: string }>('/databases/clear/all?confirm=true', {
    method: 'DELETE',
  });
}

export async function importExcel(file: File, replace = false) {
  log.info('POST /databases/import', { filename: file.name, replace });
  const form = new FormData();
  form.append('file', file);
  const token = getToken();
  const res = await fetch(`${API_BASE}/databases/import?replace=${replace}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  return handleResponse<{ imported: number; skipped: number; message: string }>(
    res,
    'POST',
    '/databases/import',
  );
}

export type EmailStatus = {
  enabled: boolean;
  configured: boolean;
  provider: string;
  smtp_host: string | null;
  mail_from: string | null;
  graph_send_as: string | null;
  hint: string | null;
};

export async function getEmailStatus() {
  return request<EmailStatus>('/email/status');
}

export async function sendCustomEmail(payload: {
  to: string[];
  cc?: string[];
  subject: string;
  body: string;
  html?: boolean;
}) {
  return request<{ message: string }>('/email/send', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function notifyRecordEmail(
  recordId: number,
  payload: { to?: string; message?: string },
) {
  return request<{ message: string }>(`/email/records/${recordId}/notify`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function sendExpiryDigestEmail(payload: {
  category: KpiCategory;
  to: string[];
  cc?: string[];
  database_type?: string;
  message?: string;
}) {
  return request<{ message: string }>('/email/expiry-digest', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export type JiraStatus = {
  enabled: boolean;
  configured: boolean;
  base_url: string | null;
  hint: string | null;
};

export async function getJiraStatus() {
  return request<JiraStatus>('/jira/status');
}

export async function addJiraCommentForRecord(
  recordId: number,
  payload: { comment: string; jira_key?: string; save_jira_key?: boolean },
) {
  return request<{
    issue_key: string;
    comment_id: string;
    browse_url: string | null;
    message: string;
  }>(`/jira/databases/${recordId}/comment`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function addJiraCommentOnIssue(issueKey: string, comment: string) {
  return request<{
    issue_key: string;
    comment_id: string;
    browse_url: string | null;
    message: string;
  }>(`/jira/issues/${encodeURIComponent(issueKey)}/comment`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  });
}

export async function exportExcel() {
  log.info('GET /databases/export/excel');
  const token = getToken();
  const res = await fetch(`${API_BASE}/databases/export/excel`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    await handleResponse(res, 'GET', '/databases/export/excel');
    return;
  }
  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition');
  const match = disposition?.match(/filename="(.+)"/);
  const filename = match?.[1] || `DB_Excel_Utility_list_${new Date().toISOString().slice(0, 10)}.xlsx`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  log.info('Export downloaded', { filename });
}
