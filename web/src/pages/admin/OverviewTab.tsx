import NumberFlow from "@number-flow/react";
import { motion } from "motion/react";
import { Activity, Clapperboard, Cpu, HardDrive, RefreshCw, Server, ShieldAlert, Thermometer, Users } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Card, cx, IconButton } from "../../components/ui";
import { adminApi, type Overview } from "../../lib/api";
import { relTime, STATE_LABEL } from "../../lib/format";
import { ActionBadge, bytes, PanelTitle } from "./common";

function Tile({ icon, label, value, sub, tone, i }: { icon: ReactNode; label: string; value: number; sub: ReactNode; tone?: string; i: number }) {
  return (
    <Card initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-semibold text-muted">{label}</span>
        <span className="grid size-8 place-items-center rounded-lg bg-surface-2 text-muted [&>svg]:size-4">{icon}</span>
      </div>
      <p className={cx("mt-2 font-mono text-3xl font-bold tabular", tone)}>
        <NumberFlow value={value} />
      </p>
      <p className="mt-1 text-xs text-muted">{sub}</p>
    </Card>
  );
}

/** Cột: số job tạo mỗi ngày (một chuỗi, một màu, không cần chú thích). */
function JobsPerDay({ data }: { data: { day: string; count: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(4, ...data.map((d) => d.count));
  const top = Math.ceil(max / 2) * 2;
  const label = (d: string) => `${d.slice(8)}/${d.slice(5, 7)}`;
  return (
    <div>
      <div className="relative flex h-44 pl-7">
        {/* Lưới mờ + nhãn trục */}
        {[1, 0.5, 0].map((f) => (
          <div key={f} className="pointer-events-none absolute inset-x-0 flex items-center" style={{ top: `${(1 - f) * 100}%` }}>
            <span className="w-6 -translate-y-1/2 pr-1 text-right font-mono text-[10px] text-muted">{Math.round(top * f)}</span>
            <span className={cx("-translate-y-1/2 flex-1 border-t", f === 0 ? "border-line-strong" : "border-dashed border-line")} />
          </div>
        ))}
        <div className="relative flex flex-1 items-end gap-[2px]" onMouseLeave={() => setHover(null)}>
          {data.map((d, i) => (
            <div key={d.day} className="relative flex h-full flex-1 items-end" onMouseEnter={() => setHover(i)}>
              <motion.div
                initial={{ scaleY: 0 }}
                animate={{ scaleY: 1 }}
                transition={{ delay: 0.15 + i * 0.03, type: "spring", stiffness: 160, damping: 20 }}
                className={cx("w-full origin-bottom rounded-t-[4px] transition-opacity", d.count ? "bg-accent" : "bg-line-strong")}
                style={{ height: d.count ? `${(d.count / top) * 100}%` : 2, opacity: hover == null || hover === i ? 1 : 0.45 }}
              />
              {hover === i && (
                <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs whitespace-nowrap shadow-lg">
                  <p className="text-muted">{label(d.day)}</p>
                  <p className="font-semibold text-ink">{d.count} job</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="mt-1.5 flex pl-7 font-mono text-[10px] text-muted">
        {data.map((d, i) => (
          <span key={d.day} className="flex-1 text-center">
            {i === data.length - 1 ? "nay" : i % 3 === 1 ? label(d.day) : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

const STATE_COLOR: Record<string, string> = {
  done: "var(--color-ok)",
  running: "var(--color-accent)",
  queued: "var(--color-spk-3)",
  created: "var(--color-line-strong)",
  error: "var(--color-rec)",
  unknown: "var(--color-muted)",
};

/** Thanh xếp chồng: tỉ lệ job theo trạng thái, có chú thích kèm số. */
function StateBreakdown({ byState, total }: { byState: Record<string, number>; total: number }) {
  const order = ["done", "running", "queued", "created", "error", "unknown"].filter((k) => byState[k]);
  if (!total) return <p className="py-6 text-center text-sm text-muted">Chưa có job nào.</p>;
  return (
    <div>
      <div className="flex h-3 gap-[2px] overflow-hidden rounded-[4px]">
        {order.map((k, i) => (
          <motion.span
            key={k}
            title={`${STATE_LABEL[k as keyof typeof STATE_LABEL] ?? k}: ${byState[k]}`}
            initial={{ flexGrow: 0 }}
            animate={{ flexGrow: byState[k] }}
            transition={{ delay: 0.2 + i * 0.06, duration: 0.6 }}
            className="h-full basis-0"
            style={{ background: STATE_COLOR[k] }}
          />
        ))}
      </div>
      <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2">
        {order.map((k) => (
          <li key={k} className="flex items-center gap-2 text-sm">
            <span className="size-2.5 rounded-[3px]" style={{ background: STATE_COLOR[k] }} />
            <span className="text-muted">{STATE_LABEL[k as keyof typeof STATE_LABEL] ?? k}</span>
            <span className="ml-auto font-mono font-semibold tabular">{byState[k]}</span>
            <span className="w-9 text-right font-mono text-[11px] text-muted">{Math.round((100 * byState[k]) / total)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Meter({ label, value, max, text, warnAt = 0.85 }: { label: string; value: number; max: number; text: string; warnAt?: number }) {
  const f = max ? value / max : 0;
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span className="font-mono text-xs font-semibold">{text}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-2">
        <motion.div className={cx("h-full rounded-full", f > warnAt ? "bg-warn" : "bg-ink/70")} initial={{ width: 0 }} animate={{ width: `${Math.min(1, f) * 100}%` }} transition={{ duration: 0.8, ease: [0.2, 0.8, 0.2, 1] }} />
      </div>
    </div>
  );
}

export function OverviewTab() {
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(false);
  const load = () => {
    setLoading(true);
    adminApi
      .overview()
      .then(setData)
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  if (!data)
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className={cx("shimmer rounded-2xl", i < 4 ? "h-28" : "h-56 sm:col-span-2")} />
        ))}
      </div>
    );

  const running = (data.jobs.by_state.running ?? 0) + (data.jobs.by_state.queued ?? 0);
  return (
    <>
      <PanelTitle
        title="Tổng quan"
        desc="Tình trạng hệ thống, tự cập nhật mỗi 15 giây."
        actions={
          <IconButton label="Làm mới" onClick={load}>
            <RefreshCw className={cx("size-4", loading && "animate-spin")} />
          </IconButton>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Tile i={0} icon={<Users />} label="Người dùng" value={data.users.total} sub={<>{data.users.online} đang trực tuyến · {data.users.admins} quản trị</>} />
        <Tile i={1} icon={<Clapperboard />} label="Job lồng tiếng" value={data.jobs.total} sub={<>{running} đang chờ/chạy · {data.jobs.by_state.error ?? 0} lỗi</>} />
        <Tile i={2} icon={<HardDrive />} label="Dữ liệu job (MB)" value={Math.round(data.jobs.storage_bytes / 2 ** 20)} sub={<>Ổ đĩa còn trống {bytes(data.disk.free)}</>} />
        <Tile
          i={3}
          icon={<ShieldAlert />}
          label="Đăng nhập sai (24 giờ)"
          value={data.security.failed_logins_24h}
          tone={data.security.failed_logins_24h >= 10 ? "text-rec" : undefined}
          sub={data.users.disabled ? `${data.users.disabled} tài khoản đang bị khoá` : "Không có tài khoản bị khoá"}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="p-5 xl:col-span-2">
          <h2 className="font-bold">Job mới mỗi ngày</h2>
          <p className="mb-5 text-xs text-muted">14 ngày gần nhất · {data.jobs.per_day.reduce((a, d) => a + d.count, 0)} job</p>
          <JobsPerDay data={data.jobs.per_day} />
        </Card>
        <Card initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="p-5">
          <h2 className="font-bold">Trạng thái job</h2>
          <p className="mb-5 text-xs text-muted">{data.jobs.total} job trên đĩa</p>
          <StateBreakdown byState={data.jobs.by_state} total={data.jobs.total} />
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="space-y-4 p-5">
          <div className="flex items-center gap-2">
            <Cpu className="size-4 text-muted" />
            <h2 className="font-bold">GPU</h2>
          </div>
          {data.gpu?.length ? (
            data.gpu.map((g, i) => (
              <div key={i} className="space-y-3">
                <p className="flex items-center justify-between text-sm font-semibold">
                  {g.name}
                  <span className="inline-flex items-center gap-1 font-mono text-xs text-muted">
                    <Thermometer className="size-3.5" />
                    {g.temp}°C
                  </span>
                </p>
                <Meter label="Tải GPU" value={g.util} max={100} text={`${g.util}%`} />
                <Meter label="VRAM" value={g.mem_used_mb} max={g.mem_total_mb} text={`${(g.mem_used_mb / 1024).toFixed(1)} / ${(g.mem_total_mb / 1024).toFixed(1)} GB`} warnAt={0.9} />
              </div>
            ))
          ) : (
            <p className="text-sm text-muted">Không tìm thấy GPU NVIDIA (nvidia-smi). Pipeline đang chạy bằng backend giả lập hoặc trên máy khác.</p>
          )}
        </Card>
        <Card initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }} className="space-y-4 p-5">
          <div className="flex items-center gap-2">
            <Server className="size-4 text-muted" />
            <h2 className="font-bold">Máy chủ</h2>
          </div>
          <Meter label="Ổ đĩa chứa dữ liệu" value={data.disk.used} max={data.disk.total} text={`${bytes(data.disk.used)} / ${bytes(data.disk.total)}`} />
          <Meter label="Dữ liệu job / ổ đĩa" value={data.jobs.storage_bytes} max={data.disk.total} text={bytes(data.jobs.storage_bytes)} />
          <div className="flex items-center justify-between rounded-xl bg-surface-2/60 px-3 py-2.5 text-sm">
            <span className="text-muted">Hàng đợi</span>
            <span className="font-semibold">{data.queue === "redis" ? "Redis + RQ worker" : "Luồng nền trong API"}</span>
          </div>
        </Card>
        <Card initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="p-5">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="size-4 text-muted" />
              <h2 className="font-bold">Hoạt động gần đây</h2>
            </div>
            <a href="#/admin/audit" className="text-xs font-semibold text-accent-strong hover:underline">
              Xem nhật ký
            </a>
          </div>
          <ul className="space-y-2.5">
            {data.recent.map((a) => (
              <li key={a.id} className="flex items-center gap-2 text-sm">
                <ActionBadge action={a.action} />
                <span className="min-w-0 flex-1 truncate text-muted">{a.email ?? a.target ?? "—"}</span>
                <span className="shrink-0 text-[11px] text-muted">{relTime(new Date(a.ts * 1000))}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
