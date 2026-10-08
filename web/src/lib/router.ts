import { useSyncExternalStore } from "react";

// Router theo hash: FastAPI chỉ cần phục vụ index.html.
//   #/                 dự án của tôi
//   #/jobs/<id>        phòng biên tập
//   #/login?next=...   đăng nhập (next: trang quay lại sau khi đăng nhập)
//   #/register  #/setup  #/account  #/admin/<tab>
export type AdminTab = "overview" | "users" | "jobs" | "audit" | "settings";
export const ADMIN_TABS: AdminTab[] = ["overview", "users", "jobs", "audit", "settings"];

export type Route =
  | { name: "home" }
  | { name: "job"; id: string }
  | { name: "login"; next?: string }
  | { name: "register" }
  | { name: "setup" }
  | { name: "account" }
  | { name: "admin"; tab: AdminTab }
  | { name: "notfound" };

function parse(): Route {
  const [path, query = ""] = location.hash.replace(/^#/, "").split("?");
  const p = path || "/";
  let m: RegExpExecArray | null;
  if (p === "/") return { name: "home" };
  if ((m = /^\/jobs\/([\w-]+)$/.exec(p))) return { name: "job", id: m[1] };
  if (p === "/login") {
    const next = new URLSearchParams(query).get("next") ?? undefined;
    // Chỉ nhận đường dẫn nội bộ dạng #/..., tránh chuyển hướng ra ngoài.
    return { name: "login", next: next && /^#\/[\w\-/]*$/.test(next) ? next : undefined };
  }
  if (p === "/register") return { name: "register" };
  if (p === "/setup") return { name: "setup" };
  if (p === "/account") return { name: "account" };
  if ((m = /^\/admin(?:\/(\w+))?$/.exec(p))) {
    const tab = (m[1] ?? "overview") as AdminTab;
    return ADMIN_TABS.includes(tab) ? { name: "admin", tab } : { name: "notfound" };
  }
  return { name: "notfound" };
}

let route = parse();
const listeners = new Set<() => void>();
addEventListener("hashchange", () => {
  const prev = route;
  const go = () => {
    route = parse();
    listeners.forEach((l) => l());
  };
  // Đổi tab trong trang quản trị thì không cần hiệu ứng chuyển trang.
  const sameShell = prev.name === "admin" && parse().name === "admin";
  if (!sameShell && document.startViewTransition && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const t = document.startViewTransition(go);
    t.ready.catch(() => {}); // bị bỏ qua khi có chuyển trang mới chen vào: không phải lỗi
    t.finished.catch(() => {});
  } else go();
  if (!sameShell) scrollTo({ top: 0 });
});

export function useRoute(): Route {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => route,
  );
}

export const navigate = (hash: string) => {
  location.hash = hash;
};

/** Thay URL hiện tại (không tạo mục lịch sử), dùng cho chuyển hướng bắt buộc. */
export const redirect = (hash: string) => {
  if (location.hash === hash) return;
  history.replaceState(null, "", hash);
  dispatchEvent(new HashChangeEvent("hashchange"));
};

export const currentHash = () => location.hash || "#/";
