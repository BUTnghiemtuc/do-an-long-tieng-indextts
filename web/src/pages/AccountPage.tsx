import { motion } from "motion/react";
import { Globe, KeyRound, Laptop, LogOut, Monitor, Save, ShieldCheck, Smartphone, UserRound } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { PasswordField, PasswordStrength, TextField, passwordChecks } from "../components/form";
import { Header } from "../components/Header";
import { Button, Card, cx, SpeakerAvatar } from "../components/ui";
import { authApi, type SessionInfo } from "../lib/api";
import { setUser, useAuth } from "../lib/auth";
import { relTime } from "../lib/format";

export function device(ua: string | null): { label: string; icon: ReactNode } {
  const u = ua ?? "";
  const browser = /Edg\//.test(u) ? "Edge" : /Chrome\//.test(u) ? "Chrome" : /Firefox\//.test(u) ? "Firefox" : /Safari\//.test(u) ? "Safari" : u ? "Trình duyệt khác" : "Không rõ";
  const os = /Windows/.test(u) ? "Windows" : /Android/.test(u) ? "Android" : /iPhone|iPad/.test(u) ? "iOS" : /Mac OS X/.test(u) ? "macOS" : /Linux/.test(u) ? "Linux" : "";
  const mobile = /Mobile|Android|iPhone/.test(u);
  return {
    label: os ? `${browser} · ${os}` : browser,
    icon: mobile ? <Smartphone className="size-4" /> : /Mac|Windows|Linux/.test(u) ? <Laptop className="size-4" /> : <Monitor className="size-4" />,
  };
}

export const fmtDate = (ts: number | null | undefined) =>
  ts ? new Date(ts * 1000).toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

function Section({ icon, title, desc, children, delay = 0 }: { icon: ReactNode; title: string; desc: string; children: ReactNode; delay?: number }) {
  return (
    <Card initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.45 }} className="p-5 sm:p-6">
      <div className="mb-5 flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent/12 text-accent-strong [&>svg]:size-5">{icon}</span>
        <div>
          <h2 className="font-bold">{title}</h2>
          <p className="text-sm text-muted">{desc}</p>
        </div>
      </div>
      {children}
    </Card>
  );
}

export function AccountPage() {
  const { user } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [savingName, setSavingName] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [savingPw, setSavingPw] = useState(false);
  const [sessions, setSessions] = useState<SessionInfo[] | null>(null);

  const loadSessions = useCallback(() => authApi.sessions().then(setSessions).catch(() => setSessions([])), []);
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);
  if (!user) return null;

  const pwOk = passwordChecks(next, user.email).every((c) => c.ok) && next === confirm && current.length > 0;

  return (
    <>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-8 flex items-center gap-4">
          <SpeakerAvatar name={user.name} color={user.role === "admin" ? "var(--color-accent)" : "var(--color-spk-3)"} size={64} />
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-extrabold tracking-tight sm:text-3xl">{user.name}</h1>
            <p className="truncate text-sm text-muted">
              {user.email} · {user.role === "admin" ? "Quản trị viên" : "Người biên tập"} · tham gia {new Date(user.created_at * 1000).toLocaleDateString("vi-VN")}
            </p>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Section icon={<UserRound />} title="Hồ sơ" desc="Tên hiển thị trên các dự án và nhật ký.">
            <form
              className="space-y-4"
              onSubmit={async (e) => {
                e.preventDefault();
                setSavingName(true);
                try {
                  setUser(await authApi.updateMe(name));
                  toast.success("Đã lưu hồ sơ");
                } catch (err) {
                  toast.error("Không lưu được", { description: (err as Error).message });
                } finally {
                  setSavingName(false);
                }
              }}
            >
              <TextField label="Tên hiển thị" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
              <TextField label="Email" value={user.email} disabled hint="Email dùng để đăng nhập, liên hệ quản trị viên nếu cần đổi." />
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-xl bg-surface-2/60 p-3">
                  <p className="text-xs text-muted">Dung lượng tối đa mỗi clip</p>
                  <p className="font-mono font-bold">{user.limits.max_upload_mb} MB</p>
                </div>
                <div className="rounded-xl bg-surface-2/60 p-3">
                  <p className="text-xs text-muted">Job chạy cùng lúc</p>
                  <p className="font-mono font-bold">{user.role === "admin" ? "không giới hạn" : user.limits.max_active_jobs}</p>
                </div>
              </div>
              <Button type="submit" variant="primary" size="sm" disabled={!name.trim() || name === user.name} loading={savingName} icon={<Save className="size-3.5" />}>
                Lưu hồ sơ
              </Button>
            </form>
          </Section>

          <Section icon={<KeyRound />} title="Đổi mật khẩu" desc="Đổi xong, mọi thiết bị khác sẽ bị đăng xuất." delay={0.06}>
            <form
              className="space-y-4"
              onSubmit={async (e) => {
                e.preventDefault();
                setSavingPw(true);
                try {
                  const r = await authApi.changePassword(current, next);
                  toast.success("Đã đổi mật khẩu", { description: r.revoked_sessions ? `Đã đăng xuất ${r.revoked_sessions} phiên khác.` : undefined });
                  setCurrent("");
                  setNext("");
                  setConfirm("");
                  loadSessions();
                } catch (err) {
                  toast.error("Không đổi được mật khẩu", { description: (err as Error).message });
                } finally {
                  setSavingPw(false);
                }
              }}
            >
              <PasswordField label="Mật khẩu hiện tại" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
              <div>
                <PasswordField label="Mật khẩu mới" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
                <PasswordStrength password={next} email={user.email} />
              </div>
              <PasswordField label="Nhập lại mật khẩu mới" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} error={confirm && confirm !== next ? "Chưa khớp" : null} />
              <Button type="submit" variant="primary" size="sm" disabled={!pwOk} loading={savingPw} icon={<ShieldCheck className="size-3.5" />}>
                Đổi mật khẩu
              </Button>
            </form>
          </Section>

          <Section icon={<Globe />} title="Phiên đăng nhập" desc="Các thiết bị đang đăng nhập vào tài khoản này. Thấy lạ thì đăng xuất ngay và đổi mật khẩu." delay={0.12}>
            <div className="space-y-2 lg:col-span-2">
              {sessions === null
                ? [0, 1].map((i) => <div key={i} className="shimmer h-16 rounded-xl" />)
                : sessions.map((s) => {
                    const d = device(s.user_agent);
                    return (
                      <motion.div layout key={s.id} className={cx("flex items-center gap-3 rounded-xl border p-3", s.current ? "border-accent/50 bg-accent/5" : "border-line")}>
                        <span className="grid size-9 place-items-center rounded-lg bg-surface-2 text-muted">{d.icon}</span>
                        <div className="min-w-0 flex-1">
                          <p className="flex items-center gap-2 text-sm font-semibold">
                            {d.label}
                            {s.current && <span className="rounded-full bg-ok/12 px-2 py-0.5 text-[10px] font-bold text-ok">Thiết bị này</span>}
                          </p>
                          <p className="truncate text-xs text-muted">
                            IP {s.ip} · hoạt động {relTime(new Date(s.last_seen_at * 1000))} · hết hạn {fmtDate(s.expires_at)}
                          </p>
                        </div>
                        {!s.current && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={async () => {
                              await authApi.revokeSession(s.id);
                              toast.success("Đã đăng xuất thiết bị");
                              loadSessions();
                            }}
                          >
                            Đăng xuất
                          </Button>
                        )}
                      </motion.div>
                    );
                  })}
              {sessions && sessions.length > 1 && (
                <Button
                  size="sm"
                  variant="danger"
                  className="mt-2"
                  icon={<LogOut className="size-3.5" />}
                  onClick={async () => {
                    const r = await authApi.revokeOthers();
                    toast.success(`Đã đăng xuất ${r.revoked} thiết bị khác`);
                    loadSessions();
                  }}
                >
                  Đăng xuất mọi thiết bị khác
                </Button>
              )}
            </div>
          </Section>

          <Section icon={<ShieldCheck />} title="Bảo mật tài khoản" desc="Những gì hệ thống đang làm để bảo vệ bạn." delay={0.18}>
            <ul className="space-y-2.5 text-sm">
              {[
                "Mật khẩu băm bằng scrypt có muối, không ai đọc được, kể cả quản trị viên.",
                "Cookie phiên HttpOnly + SameSite, JavaScript trên trang không đọc được.",
                "Chống giả mạo yêu cầu (CSRF) ở mọi thao tác ghi.",
                "Khoá tạm 15 phút sau 5 lần nhập sai mật khẩu.",
                "Chỉ bạn (và quản trị viên) xem được clip và bản dịch của bạn.",
              ].map((t) => (
                <li key={t} className="flex gap-2.5">
                  <ShieldCheck className="mt-0.5 size-4 shrink-0 text-ok" />
                  <span className="text-muted">{t}</span>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      </main>
    </>
  );
}
