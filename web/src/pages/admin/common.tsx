import type { ReactNode } from "react";
import { cx } from "../../components/ui";

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const u = ["KB", "MB", "GB", "TB"];
  let i = -1;
  do {
    n /= 1024;
    i++;
  } while (n >= 1024 && i < u.length - 1);
  return `${n.toFixed(n < 10 ? 1 : 0)} ${u[i]}`;
}

type Tone = "danger" | "warn" | "ok" | "neutral";

export const ACTIONS: Record<string, { label: string; tone: Tone }> = {
  login: { label: "Đăng nhập", tone: "ok" },
  logout: { label: "Đăng xuất", tone: "neutral" },
  login_failed: { label: "Đăng nhập sai", tone: "danger" },
  login_blocked: { label: "Tài khoản khoá cố đăng nhập", tone: "danger" },
  register: { label: "Đăng ký", tone: "ok" },
  setup: { label: "Khởi tạo hệ thống", tone: "ok" },
  setup_failed: { label: "Sai mã khởi tạo", tone: "danger" },
  password_change: { label: "Đổi mật khẩu", tone: "neutral" },
  password_change_failed: { label: "Đổi mật khẩu thất bại", tone: "danger" },
  session_revoke: { label: "Đăng xuất một thiết bị", tone: "neutral" },
  session_revoke_others: { label: "Đăng xuất thiết bị khác", tone: "neutral" },
  user_create: { label: "Tạo người dùng", tone: "ok" },
  user_update: { label: "Sửa người dùng", tone: "warn" },
  user_reset_password: { label: "Đặt lại mật khẩu", tone: "warn" },
  user_kick: { label: "Buộc đăng xuất", tone: "warn" },
  user_delete: { label: "Xoá người dùng", tone: "danger" },
  job_create: { label: "Tạo job", tone: "ok" },
  job_delete: { label: "Xoá job", tone: "danger" },
  settings_update: { label: "Đổi cài đặt", tone: "warn" },
};

const TONE: Record<Tone, string> = {
  danger: "bg-rec/12 text-rec",
  warn: "bg-warn/12 text-warn",
  ok: "bg-ok/12 text-ok",
  neutral: "bg-surface-2 text-muted",
};

export function ActionBadge({ action }: { action: string }) {
  const a = ACTIONS[action] ?? { label: action, tone: "neutral" as Tone };
  return <span className={cx("inline-flex rounded-full px-2 py-0.5 text-[11px] font-bold whitespace-nowrap", TONE[a.tone])}>{a.label}</span>;
}

export function PanelTitle({ title, desc, actions }: { title: string; desc?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
        {desc && <p className="mt-0.5 text-sm text-muted">{desc}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Bảng dùng chung: cuộn ngang trên màn hình hẹp. */
export function Table({ head, children, empty }: { head: ReactNode[]; children: ReactNode; empty?: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-line bg-surface-2/50 text-left text-[11px] font-bold tracking-wide text-muted uppercase">
              {head.map((h, i) => (
                <th key={i} className="px-4 py-3 whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">{children}</tbody>
        </table>
      </div>
      {empty}
    </div>
  );
}

export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="h-9 w-full rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-line-strong sm:w-64"
    />
  );
}

export function Segmented<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="flex rounded-xl bg-surface-2 p-1 text-[13px] font-semibold">
      {options.map(([k, label]) => (
        <button key={k} onClick={() => onChange(k)} className={cx("rounded-lg px-3 py-1 transition", value === k ? "bg-surface text-ink shadow ring-1 ring-line" : "text-muted hover:text-ink")}>
          {label}
        </button>
      ))}
    </div>
  );
}
