import { motion, type HTMLMotionProps } from "motion/react";
import { Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import type { JobState } from "../lib/api";
import { STATE_LABEL } from "../lib/format";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

type Variant = "primary" | "ghost" | "outline" | "danger";
const VARIANT: Record<Variant, string> = {
  primary:
    "bg-accent text-accent-ink shadow-[0_8px_24px_-10px_var(--color-accent)] hover:brightness-105 active:brightness-95",
  outline: "border border-line-strong bg-surface hover:bg-surface-2",
  ghost: "hover:bg-surface-2 text-muted hover:text-ink",
  danger: "border border-rec/40 text-rec hover:bg-rec/10",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "outline", size = "md", loading, icon, className, children, disabled, ...rest },
  ref,
) {
  const sz = size === "sm" ? "h-8 px-3 text-[13px] gap-1.5" : size === "lg" ? "h-12 px-6 text-[15px] gap-2.5" : "h-10 px-4 text-sm gap-2";
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center rounded-xl font-semibold whitespace-nowrap transition-[background,filter,transform,color] duration-150 active:scale-[.97] disabled:pointer-events-none disabled:opacity-45",
        sz,
        VARIANT[variant],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});

export function IconButton({ label, className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={cx(
        "inline-grid size-9 place-items-center rounded-xl text-muted transition hover:bg-surface-2 hover:text-ink active:scale-95 disabled:opacity-40 disabled:pointer-events-none",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

const STATE_STYLE: Record<JobState, string> = {
  created: "bg-surface-2 text-muted",
  queued: "bg-accent/15 text-accent-strong",
  running: "bg-rec/12 text-rec",
  done: "bg-ok/12 text-ok",
  error: "bg-rec/12 text-rec",
  unknown: "bg-surface-2 text-muted",
};

export function StateBadge({ state, className }: { state: JobState; className?: string }) {
  const live = state === "running" || state === "queued";
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold", STATE_STYLE[state], className)}>
      <span className={cx("size-1.5 rounded-full bg-current", live && "animate-rec")} />
      {state === "running" ? "REC · " : ""}
      {STATE_LABEL[state]}
    </span>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded-md border border-line-strong bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-muted">
      {children}
    </kbd>
  );
}

/** Thẻ có ánh sáng đi theo con trỏ. */
export function Card({ className, children, ...rest }: HTMLMotionProps<"div">) {
  return (
    <motion.div
      onPointerMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
        e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
      }}
      className={cx("spotlight rounded-2xl border border-line bg-surface", className)}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

/** Thanh sóng âm nhấp nhô: biểu tượng "đang thu". */
export function EqBars({ n = 5, className, playing = true }: { n?: number; className?: string; playing?: boolean }) {
  return (
    <span className={cx("inline-flex h-4 items-end gap-[2px]", className)} aria-hidden>
      {Array.from({ length: n }, (_, i) => (
        <span
          key={i}
          className="eq-bar w-[3px] rounded-full bg-current"
          style={{ height: "100%", animationDelay: `${(i * 0.13) % 0.7}s`, animationPlayState: playing ? "running" : "paused" }}
        />
      ))}
    </span>
  );
}

/** Màu cố định cho mỗi người nói, theo thứ tự ID. */
export function speakerColor(spk: string, all: string[]): string {
  const i = Math.max(0, [...all].sort().indexOf(spk));
  return `var(--color-spk-${i % 6})`;
}

export function SpeakerAvatar({ name, color, size = 28 }: { name: string; color: string; size?: number }) {
  const auto = /^SPEAKER_(\d+)$/.exec(name);
  const initials = auto
    ? `S${+auto[1] + 1}`
    : name
      .split(/\s+/)
      .map((w) => w[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "?";
  return (
    <span
      className="inline-grid shrink-0 place-items-center rounded-full font-bold text-white"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.38,
        background: `linear-gradient(135deg, ${color}, color-mix(in oklab, ${color}, black 30%))`,
        boxShadow: `0 0 0 2px var(--color-surface), 0 0 0 3.5px color-mix(in oklab, ${color} 55%, transparent)`,
      }}
    >
      {initials}
    </span>
  );
}
