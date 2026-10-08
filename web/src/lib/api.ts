// Kiểu dữ liệu khớp vidub/project.py và server/app.py.

export type JobState = "created" | "queued" | "running" | "done" | "error" | "unknown";
export type SegmentStatus = "new" | "translated" | "synthesized" | "done" | "error";

export const STEPS = ["extract", "separate", "diarize", "transcribe", "translate", "synthesize", "align", "mix"] as const;
export type StepName = (typeof STEPS)[number];
export const BUSY: JobState[] = ["created", "queued", "running"];

export interface Status {
  state: JobState;
  step?: StepName | null;
  frac?: number;
  msg?: string;
  error?: string | null;
  trace?: string;
  steps?: StepName[] | null;
  filename?: string;
  started?: number;
  updated?: number;
}

export interface Speaker {
  name: string;
  timbre_prompt: string | null;
  notes: string;
}

export interface Segment {
  id: number;
  start: number;
  end: number;
  speaker: string;
  src_text: string;
  vi_text: string;
  max_syllables: number | null;
  vi_locked: boolean;
  style_prompt: string | null;
  tts_natural: string | null;
  natural_dur: number | null;
  tts_audio: string | null;
  place_start: number | null;
  duration_ratio: number | null;
  align_method: string[];
  status: SegmentStatus;
  warnings: string[];
}

export interface Project {
  clip_id: string;
  source: string;
  src_lang: string;
  tgt_lang: string;
  duration: number | null;
  tracks: Partial<Record<"original" | "vocals" | "background" | "dub", string>>;
  speakers: Record<string, Speaker>;
  segments: Segment[];
  steps: Partial<Record<StepName, { hash: string | null; elapsed: number; finished_at: string | null }>>;
  outputs: Partial<Record<"video" | "srt_vi" | "srt_src", string>>;
}

export interface Job {
  id: string;
  status: Status;
  project: Project;
  rtf: { clip_duration: number; processing_time: number; rtf: number | null; per_step: Record<string, number> };
}

export interface JobSummary {
  id: string;
  filename: string | null;
  state: JobState;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function cookie(name: string): string {
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : "";
}

/** Phát khi API trả 401 (phiên hết hạn / bị đăng xuất từ xa): auth.ts nghe để về trang đăng nhập. */
export const UNAUTHORIZED_EVENT = "vidub:unauthorized";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  // CSRF double-submit: cookie vidub_csrf do server đặt, gửi lại qua header ở mọi request ghi.
  if (!["GET", "HEAD"].includes(method)) headers.set("X-CSRF-Token", cookie("vidub_csrf"));
  const res = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (res.status === 401 && !path.startsWith("/api/auth/")) dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* body không phải JSON */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

// ---------------------------------------------------------------- tài khoản & quản trị
export type Role = "admin" | "user";

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  active: number;
  must_change_password: number;
  created_at: number;
  last_login_at: number | null;
}

export interface Me extends User {
  limits: { max_upload_mb: number; max_active_jobs: number };
}

export interface SessionInfo {
  id: number;
  created_at: number;
  last_seen_at: number;
  expires_at: number;
  ip: string | null;
  user_agent: string | null;
  current: boolean;
}

export interface AdminUser extends User {
  job_count: number;
  session_count: number;
}

export interface AdminJob {
  id: string;
  filename: string | null;
  state: JobState;
  step: string | null;
  error: string | null;
  owner_id: number | null;
  owner_email: string | null;
  owner_name: string | null;
  created_at: number;
  size_bytes: number;
}

export interface AuditEntry {
  id: number;
  ts: number;
  user_id: number | null;
  email: string | null;
  action: string;
  target: string | null;
  ip: string | null;
  detail: string | null;
}

export interface Overview {
  users: { total: number; admins: number; disabled: number; online: number };
  jobs: { total: number; by_state: Record<string, number>; per_day: { day: string; count: number }[]; storage_bytes: number };
  disk: { total: number; used: number; free: number };
  gpu: { name: string; mem_used_mb: number; mem_total_mb: number; util: number; temp: number }[] | null;
  queue: "redis" | "local";
  security: { failed_logins_24h: number };
  recent: AuditEntry[];
}

export interface Settings {
  allow_registration: boolean;
  max_upload_mb: number;
  max_active_jobs: number;
  session_hours: number;
  remember_days: number;
}

export const authApi = {
  status: () => request<{ setup_required: boolean; allow_registration: boolean; user: Me | null }>("/api/auth/status"),
  me: () => request<Me>("/api/auth/me"),
  login: (email: string, password: string, remember: boolean) => request<User>("/api/auth/login", json("POST", { email, password, remember })),
  register: (email: string, name: string, password: string) => request<User>("/api/auth/register", json("POST", { email, name, password })),
  setup: (email: string, name: string, password: string, token: string) =>
    request<User>("/api/auth/setup", json("POST", { email, name, password, token })),
  logout: () => request<{ ok: true }>("/api/auth/logout", { method: "POST" }),
  updateMe: (name: string) => request<Me>("/api/auth/me", json("PATCH", { name })),
  changePassword: (current: string, next: string) =>
    request<{ ok: true; revoked_sessions: number }>("/api/auth/password", json("POST", { current, new: next })),
  sessions: () => request<SessionInfo[]>("/api/auth/sessions"),
  revokeSession: (id: number) => request<{ ok: true }>(`/api/auth/sessions/${id}`, { method: "DELETE" }),
  revokeOthers: () => request<{ revoked: number }>("/api/auth/sessions/revoke-others", { method: "POST" }),
};

export const adminApi = {
  overview: () => request<Overview>("/api/admin/overview"),
  users: () => request<AdminUser[]>("/api/admin/users"),
  createUser: (body: { email: string; name: string; role: Role; password?: string }) =>
    request<{ user: User; temp_password: string | null }>("/api/admin/users", json("POST", body)),
  patchUser: (id: number, body: { name?: string; role?: Role; active?: boolean }) => request<User>(`/api/admin/users/${id}`, json("PATCH", body)),
  resetPassword: (id: number) => request<{ temp_password: string }>(`/api/admin/users/${id}/reset-password`, { method: "POST" }),
  kick: (id: number) => request<{ revoked: number }>(`/api/admin/users/${id}/sessions`, { method: "DELETE" }),
  deleteUser: (id: number) => request<{ ok: true }>(`/api/admin/users/${id}`, { method: "DELETE" }),
  jobs: () => request<AdminJob[]>("/api/admin/jobs"),
  audit: (p: { limit?: number; offset?: number; action?: string; q?: string }) => {
    const qs = new URLSearchParams(Object.entries(p).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return request<{ total: number; items: AuditEntry[]; actions: string[] }>(`/api/admin/audit?${qs}`);
  },
  settings: () => request<Settings>("/api/admin/settings"),
  patchSettings: (body: Partial<Settings>) => request<Settings>("/api/admin/settings", json("PATCH", body)),
};

export const api = {
  meta: () => request<{ disclaimer: string }>("/api/meta"),
  jobs: () => request<JobSummary[]>("/api/jobs"),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  create: (form: FormData) => request<{ id: string }>("/api/jobs", { method: "POST", body: form }),
  deleteJob: (id: string) => request<{ ok: true }>(`/api/jobs/${id}`, { method: "DELETE" }),
  render: (id: string) => request<{ ok: true }>(`/api/jobs/${id}/render`, { method: "POST" }),
  rerun: (id: string, fromStep: StepName, force: boolean) =>
    request<{ ok: true }>(`/api/jobs/${id}/rerun?from_step=${fromStep}&force=${force}`, { method: "POST" }),
  patchSpeaker: (id: string, spk: string, body: { name?: string; notes?: string; timbre_from_segment?: number }) =>
    request<Job>(`/api/jobs/${id}/speakers/${encodeURIComponent(spk)}`, json("PATCH", body)),
  patchSegment: (id: string, seg: number, body: { vi_text?: string; speaker?: string; unlock?: boolean }) =>
    request<Job>(`/api/jobs/${id}/segments/${seg}`, json("PATCH", body)),
  regenerate: (id: string, seg: number) =>
    request<{ ok: true }>(`/api/jobs/${id}/segments/${seg}/regenerate`, { method: "POST" }),
};

export const sourceUrl = (id: string) => `/api/jobs/${id}/source`;

/** URL file trong dự án. `v` để trình duyệt không dùng bản cache cũ sau khi sinh lại. */
export const fileUrl = (id: string, rel: string | null | undefined, v?: number | string) =>
  rel ? `/api/jobs/${id}/files/${rel}${v != null ? `?v=${encodeURIComponent(v)}` : ""}` : undefined;

export const isBusy = (s: Status | undefined) => !!s && BUSY.includes(s.state);
