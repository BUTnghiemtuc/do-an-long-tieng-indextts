import { motion } from "motion/react";
import { Clapperboard, LayoutDashboard, ScrollText, Settings, Users } from "lucide-react";
import { Header } from "../../components/Header";
import { cx } from "../../components/ui";
import type { AdminTab } from "../../lib/router";
import { AuditTab } from "./AuditTab";
import { JobsTab } from "./JobsTab";
import { OverviewTab } from "./OverviewTab";
import { SettingsTab } from "./SettingsTab";
import { UsersTab } from "./UsersTab";

const TABS: { id: AdminTab; label: string; icon: typeof Users }[] = [
  { id: "overview", label: "Tổng quan", icon: LayoutDashboard },
  { id: "users", label: "Người dùng", icon: Users },
  { id: "jobs", label: "Job", icon: Clapperboard },
  { id: "audit", label: "Nhật ký", icon: ScrollText },
  { id: "settings", label: "Cài đặt", icon: Settings },
];

export function AdminPage({ tab }: { tab: AdminTab }) {
  return (
    <>
      <Header />
      <div className="mx-auto grid max-w-[1440px] grid-cols-1 gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="min-w-0 lg:sticky lg:top-24 lg:self-start">
          <p className="mb-2 hidden px-3 text-[11px] font-bold tracking-wider text-muted uppercase lg:block">Quản trị</p>
          <nav className="-mx-4 flex gap-1 overflow-x-auto px-4 lg:mx-0 lg:flex-col lg:px-0">
            {TABS.map((t) => (
              <a
                key={t.id}
                href={`#/admin/${t.id}`}
                aria-current={tab === t.id ? "page" : undefined}
                className={cx("relative flex shrink-0 items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-semibold transition", tab === t.id ? "text-ink" : "text-muted hover:bg-surface-2 hover:text-ink")}
              >
                {tab === t.id && <motion.span layoutId="admin-tab" className="absolute inset-0 rounded-xl bg-surface shadow-sm ring-1 ring-line" transition={{ type: "spring", stiffness: 500, damping: 38 }} />}
                <t.icon className={cx("relative size-4", tab === t.id && "text-accent-strong")} />
                <span className="relative">{t.label}</span>
              </a>
            ))}
          </nav>
        </aside>
        <motion.main key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="min-w-0">
          {tab === "overview" && <OverviewTab />}
          {tab === "users" && <UsersTab />}
          {tab === "jobs" && <JobsTab />}
          {tab === "audit" && <AuditTab />}
          {tab === "settings" && <SettingsTab />}
        </motion.main>
      </div>
    </>
  );
}
