import { useCallback, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";
const KEY = "vidub-theme";

const listeners = new Set<() => void>();
const current = (): Theme => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* trình duyệt chặn storage: vẫn đổi được trong phiên này */
  }
  listeners.forEach((l) => l());
}

/**
 * Đổi theme bằng View Transitions API: trang mới "loé" ra thành vòng tròn từ nút bấm,
 * giống ánh đèn chiếu bật lên. Trình duyệt không hỗ trợ hoặc người dùng giảm chuyển động
 * thì đổi ngay.
 */
export function useTheme() {
  const theme = useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    current,
    () => "dark" as Theme,
  );

  const toggle = useCallback((origin?: HTMLElement | null) => {
    const next: Theme = current() === "dark" ? "light" : "dark";
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!document.startViewTransition || reduce) {
      apply(next);
      return;
    }
    const r = origin?.getBoundingClientRect();
    const x = r ? r.left + r.width / 2 : innerWidth / 2;
    const y = r ? r.top + r.height / 2 : 0;
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));

    const html = document.documentElement;
    html.classList.add("theme-vt");
    const t = document.startViewTransition(() => apply(next));
    t.finished.catch(() => {}).finally(() => html.classList.remove("theme-vt"));
    t.ready
      .then(() => {
        document.documentElement.animate(
          { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
          { duration: 650, easing: "cubic-bezier(.7,0,.2,1)", pseudoElement: "::view-transition-new(root)" },
        );
      })
      .catch(() => {}); // chuyển tiếp bị bỏ qua: theme vẫn đã đổi
  }, []);

  return { theme, toggle };
}

/** Đọc giá trị màu thật từ biến CSS (cho canvas của wavesurfer). */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
