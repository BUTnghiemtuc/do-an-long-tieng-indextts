import { AnimatePresence, motion } from "motion/react";
import { ArrowBigUpDash, Check, Eye, EyeOff, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cx } from "./ui";

// ---------------------------------------------------------------- ô nhập
interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label: string;
  icon?: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  trailing?: ReactNode;
}

export function TextField({ label, icon, hint, error, trailing, className, id, ...rest }: FieldProps) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <div className={className}>
      <label htmlFor={fid} className="mb-1.5 block text-[13px] font-semibold">
        {label}
      </label>
      <div
        className={cx(
          "flex h-11 items-center gap-2.5 rounded-xl border bg-surface px-3 transition focus-within:ring-4",
          error ? "border-rec focus-within:ring-rec/15" : "border-line-strong focus-within:border-accent focus-within:ring-accent/15",
        )}
      >
        {icon && <span className="text-muted [&>svg]:size-4">{icon}</span>}
        <input id={fid} aria-invalid={!!error} className="h-full min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted/60 disabled:opacity-60" {...rest} />
        {trailing}
      </div>
      {error ? <p className="mt-1.5 text-xs font-medium text-rec">{error}</p> : hint ? <p className="mt-1.5 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export function PasswordField(props: FieldProps) {
  const [show, setShow] = useState(false);
  const [caps, setCaps] = useState(false);
  return (
    <TextField
      {...props}
      type={show ? "text" : "password"}
      onKeyUp={(e) => setCaps(e.getModifierState?.("CapsLock") ?? false)}
      onBlur={() => setCaps(false)}
      hint={caps ? <span className="inline-flex items-center gap-1 font-semibold text-warn"><ArrowBigUpDash className="size-3.5" /> Đang bật Caps Lock</span> : props.hint}
      trailing={
        <button type="button" onClick={() => setShow((v) => !v)} className="text-muted hover:text-ink" aria-label={show ? "Ẩn mật khẩu" : "Hiện mật khẩu"} tabIndex={-1}>
          {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      }
    />
  );
}

/** Kiểm tra giống hệt server/security.py:password_problems để người dùng biết trước khi gửi. */
export function passwordChecks(pw: string, email = "") {
  const local = email.split("@")[0].toLowerCase();
  return [
    { ok: pw.length >= 8, label: "Ít nhất 8 ký tự" },
    { ok: /[A-Za-zÀ-ỹ]/.test(pw) && /\d/.test(pw), label: "Có cả chữ và số" },
    { ok: !(local.length >= 4 && pw.toLowerCase().includes(local)), label: "Không chứa tên email" },
  ];
}

export function PasswordStrength({ password, email }: { password: string; email?: string }) {
  const checks = passwordChecks(password, email);
  const bonus = (password.length >= 12 ? 1 : 0) + (/[^A-Za-z0-9]/.test(password) ? 1 : 0) + (/[A-Z]/.test(password) && /[a-z]/.test(password) ? 1 : 0);
  const score = password ? Math.min(4, checks.filter((c) => c.ok).length - 1 + bonus) : 0;
  const tone = ["bg-rec", "bg-rec", "bg-warn", "bg-ok", "bg-ok"][Math.max(0, score)];
  const word = ["Rất yếu", "Yếu", "Tạm được", "Mạnh", "Rất mạnh"][Math.max(0, score)];
  return (
    <div className="mt-2.5 space-y-2">
      <div className="flex items-center gap-2">
        <div className="grid flex-1 grid-cols-4 gap-1">
          {[0, 1, 2, 3].map((i) => (
            <span key={i} className="h-1 overflow-hidden rounded-full bg-surface-2">
              <motion.span className={cx("block h-full", tone)} initial={false} animate={{ width: password && i < Math.max(1, score) ? "100%" : "0%" }} transition={{ duration: 0.25, delay: i * 0.04 }} />
            </span>
          ))}
        </div>
        {password && <span className="w-16 text-right text-[11px] font-semibold text-muted">{word}</span>}
      </div>
      <ul className="grid gap-1 sm:grid-cols-3">
        {checks.map((c) => (
          <li key={c.label} className={cx("flex items-center gap-1.5 text-[11px] font-medium transition-colors", c.ok ? "text-ok" : "text-muted")}>
            <motion.span key={String(c.ok)} initial={{ scale: 0.4 }} animate={{ scale: 1 }} className={cx("grid size-3.5 place-items-center rounded-full", c.ok ? "bg-ok/15" : "bg-surface-2")}>
              {c.ok ? <Check className="size-2.5" strokeWidth={3} /> : <X className="size-2.5" strokeWidth={3} />}
            </motion.span>
            {c.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------- công tắc
export function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx("relative inline-flex h-6 w-11 shrink-0 items-center rounded-full p-0.5 transition-colors disabled:opacity-50", checked ? "bg-accent" : "bg-line-strong")}
    >
      <motion.span layout transition={{ type: "spring", stiffness: 600, damping: 34 }} className="size-5 rounded-full bg-white shadow" style={{ marginLeft: checked ? "auto" : 0 }} />
    </button>
  );
}

// ---------------------------------------------------------------- hộp thoại
export function Modal({ open, onClose, title, description, children, width = 460 }: { open: boolean; onClose: () => void; title: string; description?: ReactNode; children: ReactNode; width?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    addEventListener("keydown", onKey);
    setTimeout(() => ref.current?.querySelector<HTMLElement>("input,button[data-autofocus],textarea,select")?.focus(), 50);
    return () => {
      removeEventListener("keydown", onKey);
      prev?.focus?.();
    };
  }, [open, onClose]);
  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
            className="relative w-full rounded-3xl border border-line bg-surface p-6 shadow-2xl"
            style={{ maxWidth: width }}
          >
            <button onClick={onClose} className="absolute top-4 right-4 rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-ink" aria-label="Đóng">
              <X className="size-4" />
            </button>
            <h2 className="pr-8 text-lg font-bold">{title}</h2>
            {description && <div className="mt-1 text-sm text-muted">{description}</div>}
            <div className="mt-5">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

// ---------------------------------------------------------------- menu thả xuống
/** Menu render qua portal (vị trí fixed theo nút bấm) để không bị cắt trong bảng cuộn. */
export function Menu({ trigger, children, align = "right" }: { trigger: (open: boolean, toggle: () => void) => ReactNode; children: (close: () => void) => ReactNode; align?: "left" | "right" }) {
  const [pos, setPos] = useState<{ top: number; left?: number; right?: number; up: boolean } | null>(null);
  const anchor = useRef<HTMLSpanElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const open = pos != null;
  const close = () => setPos(null);
  const toggle = () => {
    if (open) return close();
    const r = anchor.current!.getBoundingClientRect();
    const up = r.bottom > innerHeight - 280;
    setPos({ top: up ? r.top - 8 : r.bottom + 8, up, ...(align === "right" ? { right: innerWidth - r.right } : { left: r.left }) });
  };
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!anchor.current?.contains(t) && !panel.current?.contains(t)) close();
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close();
    addEventListener("mousedown", onDown);
    addEventListener("keydown", esc);
    addEventListener("resize", close);
    addEventListener("scroll", close, true);
    return () => {
      removeEventListener("mousedown", onDown);
      removeEventListener("keydown", esc);
      removeEventListener("resize", close);
      removeEventListener("scroll", close, true);
    };
  }, [open]);
  return (
    <span ref={anchor} className="relative inline-block">
      {trigger(open, toggle)}
      {createPortal(
        <AnimatePresence>
          {pos && (
            <motion.div
              ref={panel}
              role="menu"
              initial={{ opacity: 0, y: pos.up ? 6 : -6, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: pos.up ? 6 : -6, scale: 0.97 }}
              transition={{ duration: 0.14 }}
              className="fixed z-[60] min-w-56 rounded-2xl border border-line bg-surface p-1.5 text-left text-ink shadow-2xl shadow-black/15"
              style={{ top: pos.top, left: pos.left, right: pos.right, translate: pos.up ? "0 -100%" : undefined, transformOrigin: `${align === "right" ? "right" : "left"} ${pos.up ? "bottom" : "top"}` }}
            >
              {children(close)}
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </span>
  );
}

export function MenuItem({ icon, children, onClick, danger, disabled }: { icon?: ReactNode; children: ReactNode; onClick: () => void; danger?: boolean; disabled?: boolean }) {
  return (
    <button
      role="menuitem"
      disabled={disabled}
      onClick={onClick}
      className={cx(
        "flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm font-medium transition disabled:opacity-40 [&>svg]:size-4",
        danger ? "text-rec hover:bg-rec/10" : "hover:bg-surface-2",
      )}
    >
      {icon}
      {children}
    </button>
  );
}
