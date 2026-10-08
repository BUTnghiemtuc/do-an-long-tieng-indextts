import { motion } from "motion/react";
import { ArrowRight, KeyRound, LogIn, Mail, ShieldCheck, UserPlus, UserRound } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";
import { PasswordField, PasswordStrength, TextField, passwordChecks } from "../components/form";
import { Logo } from "../components/Header";
import { ThemeToggle } from "../components/ThemeToggle";
import { Button, cx } from "../components/ui";
import { authApi } from "../lib/api";
import { logout, refreshAuth, useAuth } from "../lib/auth";
import { navigate, redirect } from "../lib/router";

// ---------------------------------------------------------------- khung chung
const FRAMES = [
  { en: "You never listened to me.", vi: "Anh chưa bao giờ nghe em cả.", c: "var(--color-spk-2)", g: "from-[#3b2a1a] to-[#14101f]" },
  { en: "We have to leave before dawn.", vi: "Mình phải đi trước khi trời sáng.", c: "var(--color-spk-3)", g: "from-[#1d2a3f] to-[#0c0c14]" },
  { en: "Where would we even go?", vi: "Mà mình biết đi đâu bây giờ?", c: "var(--color-spk-0)", g: "from-[#1c3330] to-[#0b0f12]" },
  { en: "Trust me. Just this once.", vi: "Tin anh. Chỉ lần này thôi.", c: "var(--color-spk-1)", g: "from-[#2b1d3f] to-[#0e0b16]" },
  { en: "It's not over yet.", vi: "Chuyện này chưa kết thúc đâu.", c: "var(--color-spk-5)", g: "from-[#3f241a] to-[#120c0b]" },
  { en: "Then let's go now.", vi: "Vậy thì đi ngay thôi.", c: "var(--color-spk-4)", g: "from-[#26331a] to-[#0d100b]" },
];

function FilmColumn({ offset, duration, reverse }: { offset: number; duration: number; reverse?: boolean }) {
  const frames = [...FRAMES.slice(offset), ...FRAMES.slice(0, offset)];
  return (
    <div className="relative overflow-hidden">
      <div className="flex flex-col gap-4" style={{ animation: `marquee-y ${duration}s linear infinite ${reverse ? "reverse" : ""}` }}>
        {[...frames, ...frames].map((f, i) => (
          <div key={i} className={cx("relative aspect-[4/3] shrink-0 overflow-hidden rounded-2xl bg-gradient-to-br ring-1 ring-white/10", f.g)}>
            <div className="absolute inset-x-0 top-0 h-3 bg-[radial-gradient(circle,#07070a_2px,transparent_2.5px)] bg-[length:14px_12px]" />
            <div className="absolute inset-x-0 bottom-0 h-3 bg-[radial-gradient(circle,#07070a_2px,transparent_2.5px)] bg-[length:14px_12px]" />
            <div className="absolute inset-x-3 bottom-5 space-y-1 text-center">
              <p className="text-[10px] text-white/45 line-through decoration-white/30">{f.en}</p>
              <p className="text-[12px] leading-snug font-semibold text-white">
                <span className="mr-1 inline-block size-1.5 rounded-full align-middle" style={{ background: f.c }} />
                {f.vi}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AuthLayout({ children, title, subtitle }: { children: ReactNode; title: string; subtitle: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.05fr_1fr]">
      {/* Bên trái: luôn tối như phòng chiếu */}
      <aside className="relative hidden overflow-hidden bg-[#07070a] text-[#f3efe7] lg:block">
        <div className="absolute inset-0 grid grid-cols-3 gap-4 p-4 opacity-70 [mask-image:linear-gradient(to_bottom,transparent,black_18%,black_70%,transparent)]">
          <FilmColumn offset={0} duration={38} />
          <FilmColumn offset={2} duration={46} reverse />
          <FilmColumn offset={4} duration={42} />
        </div>
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_100%,rgba(245,184,75,.28),transparent_55%)]" />
        <div className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-[#07070a] via-[#07070a]/85 to-transparent" />
        <div className="relative flex h-full flex-col justify-end p-10 xl:p-14">
          <motion.h2 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }} className="max-w-lg text-4xl leading-tight font-extrabold tracking-tight xl:text-5xl">
            Mỗi nhân vật, <span className="bg-gradient-to-r from-[#ffc768] via-[#ff4d61] to-[#a78bfa] bg-clip-text text-transparent">một giọng Việt</span>.
          </motion.h2>
          <p className="mt-4 max-w-md text-[15px] text-white/60">Tách giọng, dịch theo ngữ cảnh, sinh giọng khớp thời lượng bằng IndexTTS. Bạn chỉ cần biên tập lại những câu chưa ưng.</p>
          <div className="mt-8 flex flex-wrap gap-x-8 gap-y-3 text-sm text-white/70">
            {[
              ["8 bước", "tự động hoá"],
              ["±10%", "lệch thời lượng"],
              ["1 câu", "sửa là sinh lại"],
            ].map(([a, b]) => (
              <div key={a}>
                <p className="font-mono text-xl font-bold text-[#ffc768]">{a}</p>
                <p className="text-xs">{b}</p>
              </div>
            ))}
          </div>
        </div>
      </aside>

      {/* Bên phải: form */}
      <main className="relative flex flex-col px-5 py-6 sm:px-10">
        <div className="flex items-center justify-between">
          <Logo />
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-center justify-center py-10">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }} className="w-full max-w-[420px]">
            <h1 className="text-3xl font-extrabold tracking-tight">{title}</h1>
            <div className="mt-2 text-[15px] text-muted">{subtitle}</div>
            <div className="mt-8">{children}</div>
          </motion.div>
        </div>
        <p className="text-center text-xs text-muted">
          <ShieldCheck className="mr-1 inline size-3.5" />
          Phiên đăng nhập mã hoá cookie HttpOnly · Giọng nói do AI tạo, chỉ dùng cho nghiên cứu
        </p>
      </main>
    </div>
  );
}

/** Khung form: rung lắc khi lỗi. */
function AuthForm({ onSubmit, error, children }: { onSubmit: () => Promise<void>; error: string | null; children: ReactNode }) {
  const [n, setN] = useState(0);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await onSubmit();
    } catch {
      setN((x) => x + 1);
    }
  };
  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      {error && (
        <div key={n} role="alert" className="rounded-xl border border-rec/30 bg-rec/8 px-3.5 py-2.5 text-sm font-medium text-rec" style={{ animation: "shake .45s" }}>
          {error}
        </div>
      )}
      {children}
    </form>
  );
}

const errMsg = (e: unknown) => (e as Error).message || "Có lỗi xảy ra";

// ---------------------------------------------------------------- đăng nhập
export function LoginPage({ next }: { next?: string }) {
  const { allowRegistration } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (!email || !password) {
      setError("Nhập email và mật khẩu");
      throw new Error();
    }
    setBusy(true);
    try {
      await authApi.login(email, password, remember);
      const st = await refreshAuth();
      toast.success(`Chào mừng trở lại, ${st.user?.name ?? ""}`);
      redirect(next ?? "#/");
    } catch (e) {
      setError(errMsg(e));
      throw e;
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      title="Đăng nhập"
      subtitle={
        allowRegistration ? (
          <>
            Chưa có tài khoản?{" "}
            <a href="#/register" className="font-semibold text-accent-strong hover:underline">
              Đăng ký miễn phí
            </a>
          </>
        ) : (
          "Vào phòng lồng tiếng của bạn."
        )
      }
    >
      <AuthForm onSubmit={submit} error={error}>
        <TextField label="Email" type="email" autoComplete="username" icon={<Mail />} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ban@vidu.vn" autoFocus />
        <PasswordField label="Mật khẩu" autoComplete="current-password" icon={<KeyRound />} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        <div className="flex items-center justify-between text-sm">
          <label className="flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
            Ghi nhớ đăng nhập
          </label>
          <button type="button" className="font-medium text-muted hover:text-ink" onClick={() => toast("Quên mật khẩu?", { description: "Liên hệ quản trị viên để được cấp mật khẩu tạm." })}>
            Quên mật khẩu?
          </button>
        </div>
        <Button type="submit" variant="primary" size="lg" className="w-full" loading={busy} icon={<LogIn className="size-5" />}>
          Đăng nhập
        </Button>
      </AuthForm>
    </AuthLayout>
  );
}

// ---------------------------------------------------------------- đăng ký
export function RegisterPage() {
  const { allowRegistration } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!allowRegistration)
    return (
      <AuthLayout title="Đăng ký đang tắt" subtitle="Quản trị viên chỉ cấp tài khoản theo yêu cầu.">
        <Button variant="outline" size="lg" className="w-full" onClick={() => navigate("#/login")} icon={<LogIn className="size-5" />}>
          Về trang đăng nhập
        </Button>
      </AuthLayout>
    );

  const submit = async () => {
    setError(null);
    if (!passwordChecks(password, email).every((c) => c.ok)) {
      setError("Mật khẩu chưa đạt yêu cầu");
      throw new Error();
    }
    if (password !== confirm) {
      setError("Hai mật khẩu không khớp");
      throw new Error();
    }
    setBusy(true);
    try {
      await authApi.register(email, name, password);
      await refreshAuth();
      toast.success("Tạo tài khoản thành công", { description: "Tải clip đầu tiên để bắt đầu lồng tiếng." });
      redirect("#/");
    } catch (e) {
      setError(errMsg(e));
      throw e;
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      title="Tạo tài khoản"
      subtitle={
        <>
          Đã có tài khoản?{" "}
          <a href="#/login" className="font-semibold text-accent-strong hover:underline">
            Đăng nhập
          </a>
        </>
      }
    >
      <AuthForm onSubmit={submit} error={error}>
        <TextField label="Tên hiển thị" autoComplete="name" icon={<UserRound />} value={name} onChange={(e) => setName(e.target.value)} placeholder="Nguyễn Văn A" maxLength={80} autoFocus />
        <TextField label="Email" type="email" autoComplete="email" icon={<Mail />} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ban@vidu.vn" />
        <div>
          <PasswordField label="Mật khẩu" autoComplete="new-password" icon={<KeyRound />} value={password} onChange={(e) => setPassword(e.target.value)} />
          <PasswordStrength password={password} email={email} />
        </div>
        <PasswordField
          label="Nhập lại mật khẩu"
          autoComplete="new-password"
          icon={<KeyRound />}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={confirm && confirm !== password ? "Chưa khớp với mật khẩu ở trên" : null}
        />
        <Button type="submit" variant="primary" size="lg" className="w-full" loading={busy} icon={<UserPlus className="size-5" />}>
          Tạo tài khoản
        </Button>
      </AuthForm>
    </AuthLayout>
  );
}

// ---------------------------------------------------------------- khởi tạo lần đầu
export function SetupPage() {
  const [token, setToken] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (!passwordChecks(password, email).every((c) => c.ok)) {
      setError("Mật khẩu chưa đạt yêu cầu");
      throw new Error();
    }
    setBusy(true);
    try {
      await authApi.setup(email, name, password, token);
      await refreshAuth();
      toast.success("Đã tạo tài khoản quản trị", { description: "Vào trang Quản trị để cấu hình hệ thống." });
      redirect("#/admin");
    } catch (e) {
      setError(errMsg(e));
      throw e;
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      title="Khởi tạo hệ thống"
      subtitle={
        <>
          Tạo tài khoản <b className="text-ink">quản trị viên</b> đầu tiên. Mã khởi tạo được in trong log khi server khởi động (hoặc biến <code className="rounded bg-surface-2 px-1 font-mono text-xs">VIDUB_SETUP_TOKEN</code>).
        </>
      }
    >
      <AuthForm onSubmit={submit} error={error}>
        <TextField label="Mã khởi tạo" icon={<ShieldCheck />} value={token} onChange={(e) => setToken(e.target.value)} placeholder="dán mã từ log server" autoFocus className="[&_input]:font-mono" />
        <TextField label="Tên hiển thị" icon={<UserRound />} value={name} onChange={(e) => setName(e.target.value)} placeholder="Quản trị viên" />
        <TextField label="Email" type="email" autoComplete="email" icon={<Mail />} value={email} onChange={(e) => setEmail(e.target.value)} />
        <div>
          <PasswordField label="Mật khẩu" autoComplete="new-password" icon={<KeyRound />} value={password} onChange={(e) => setPassword(e.target.value)} />
          <PasswordStrength password={password} email={email} />
        </div>
        <Button type="submit" variant="primary" size="lg" className="w-full" loading={busy} icon={<ArrowRight className="size-5" />}>
          Tạo quản trị viên
        </Button>
      </AuthForm>
    </AuthLayout>
  );
}

// ---------------------------------------------------------------- bắt buộc đổi mật khẩu tạm
export function ForceChangePassword() {
  const { user } = useAuth();
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (!passwordChecks(password, user?.email).every((c) => c.ok)) {
      setError("Mật khẩu mới chưa đạt yêu cầu");
      throw new Error();
    }
    setBusy(true);
    try {
      await authApi.changePassword(current, password);
      await refreshAuth();
      toast.success("Đã đổi mật khẩu");
    } catch (e) {
      setError(errMsg(e));
      throw e;
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title="Đặt mật khẩu mới" subtitle={<>Tài khoản <b className="text-ink">{user?.email}</b> đang dùng mật khẩu tạm do quản trị viên cấp. Đặt mật khẩu riêng để tiếp tục.</>}>
      <AuthForm onSubmit={submit} error={error}>
        <PasswordField label="Mật khẩu tạm" autoComplete="current-password" icon={<KeyRound />} value={current} onChange={(e) => setCurrent(e.target.value)} autoFocus />
        <div>
          <PasswordField label="Mật khẩu mới" autoComplete="new-password" icon={<KeyRound />} value={password} onChange={(e) => setPassword(e.target.value)} />
          <PasswordStrength password={password} email={user?.email} />
        </div>
        <Button type="submit" variant="primary" size="lg" className="w-full" loading={busy} icon={<ShieldCheck className="size-5" />}>
          Lưu và tiếp tục
        </Button>
        <button type="button" onClick={() => logout()} className="w-full text-center text-sm font-medium text-muted hover:text-ink">
          Đăng xuất
        </button>
      </AuthForm>
    </AuthLayout>
  );
}
