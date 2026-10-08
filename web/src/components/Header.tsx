import { ChevronDown, Clapperboard, LayoutDashboard, LogOut, ShieldCheck, UserRound } from "lucide-react";
import type { ReactNode } from "react";
import { toast } from "sonner";
import { logout, useAuth } from "../lib/auth";
import { navigate, useRoute } from "../lib/router";
import { Menu, MenuItem } from "./form";
import { ThemeToggle } from "./ThemeToggle";
import { cx, SpeakerAvatar } from "./ui";

export function Logo() {
  return (
    <button onClick={() => navigate("#/")} className="group flex items-center gap-2.5" aria-label="Về trang chủ">
      <span className="relative grid size-9 place-items-center overflow-hidden rounded-xl bg-ink text-bg">
        <svg viewBox="0 0 24 24" className="size-5" aria-hidden>
          {[
            [3, 9, 6],
            [7.5, 6, 12],
            [12, 3, 18],
            [16.5, 7, 10],
          ].map(([x, y, h], i) => (
            <rect
              key={i}
              x={x}
              y={y}
              width="2.6"
              height={h}
              rx="1.3"
              className="eq-bar fill-accent"
              style={{ animationDelay: `${i * 0.15}s`, animationPlayState: "paused", transformBox: "fill-box" }}
            />
          ))}
        </svg>
        <span className="absolute top-1.5 right-1.5 size-1.5 rounded-full bg-rec" />
      </span>
      <span className="hidden text-left leading-none sm:block">
        <span className="block text-[17px] font-extrabold tracking-tight">
          vidub<span className="text-accent-strong">.</span>
        </span>
        <span className="text-[11px] font-medium text-muted">Phòng lồng tiếng AI</span>
      </span>
      <style>{`.group:hover .eq-bar{animation-play-state:running!important}`}</style>
    </button>
  );
}

function UserMenu() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <Menu
      trigger={(open, toggle) => (
        <button onClick={toggle} aria-expanded={open} aria-haspopup="menu" className="flex items-center gap-2 rounded-full border border-line bg-surface py-1 pr-2.5 pl-1 transition hover:border-line-strong">
          <SpeakerAvatar name={user.name} color={user.role === "admin" ? "var(--color-accent)" : "var(--color-spk-3)"} size={28} />
          <span className="hidden max-w-32 truncate text-sm font-semibold md:block">{user.name}</span>
          <ChevronDown className={cx("size-3.5 text-muted transition", open && "rotate-180")} />
        </button>
      )}
    >
      {(close) => (
        <>
          <div className="mb-1 border-b border-line px-3 pt-2 pb-3">
            <p className="truncate text-sm font-bold">{user.name}</p>
            <p className="truncate text-xs text-muted">{user.email}</p>
            {user.role === "admin" && (
              <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[11px] font-bold text-accent-strong">
                <ShieldCheck className="size-3" /> Quản trị viên
              </span>
            )}
          </div>
          <MenuItem icon={<Clapperboard />} onClick={() => (close(), navigate("#/"))}>
            Dự án của tôi
          </MenuItem>
          <MenuItem icon={<UserRound />} onClick={() => (close(), navigate("#/account"))}>
            Tài khoản & bảo mật
          </MenuItem>
          {user.role === "admin" && (
            <MenuItem icon={<LayoutDashboard />} onClick={() => (close(), navigate("#/admin"))}>
              Trang quản trị
            </MenuItem>
          )}
          <div className="my-1 border-t border-line" />
          <MenuItem
            icon={<LogOut />}
            danger
            onClick={async () => {
              close();
              await logout();
              toast("Đã đăng xuất");
            }}
          >
            Đăng xuất
          </MenuItem>
        </>
      )}
    </Menu>
  );
}

function NavLink({ href, active, icon, children }: { href: string; active: boolean; icon: ReactNode; children: ReactNode }) {
  return (
    <a href={href} aria-current={active ? "page" : undefined} className={cx("relative inline-flex items-center gap-1.5 rounded-lg px-3 py-2 transition [&>svg]:size-4", active ? "text-ink" : "hover:bg-surface-2 hover:text-ink")}>
      {icon}
      {children}
      {active && <span className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full bg-accent" />}
    </a>
  );
}

export function Header({ children }: { children?: ReactNode }) {
  const route = useRoute();
  const { user } = useAuth();
  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-bg/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-4 px-4 sm:px-6">
        <Logo />
        <div className="flex min-w-0 flex-1 items-center gap-3">{children}</div>
        <nav className="hidden items-center gap-1 text-sm font-medium text-muted md:flex">
          <NavLink href="#/" active={route.name === "home" || route.name === "job"} icon={<Clapperboard />}>
            Dự án
          </NavLink>
          {user?.role === "admin" && (
            <NavLink href="#/admin" active={route.name === "admin"} icon={<LayoutDashboard />}>
              Quản trị
            </NavLink>
          )}
        </nav>
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
