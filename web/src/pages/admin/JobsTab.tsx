import { motion } from "motion/react";
import { ExternalLink, RefreshCw, Trash } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Modal } from "../../components/form";
import { Button, IconButton, StateBadge } from "../../components/ui";
import { adminApi, api, BUSY, sourceUrl, type AdminJob, type JobState } from "../../lib/api";
import { relTime } from "../../lib/format";
import { navigate } from "../../lib/router";
import { fmtDate } from "../AccountPage";
import { bytes, PanelTitle, SearchBox, Segmented, Table } from "./common";

type Filter = "all" | "active" | "done" | "error" | "orphan";

export function JobsTab() {
  const [jobs, setJobs] = useState<AdminJob[] | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [deleting, setDeleting] = useState<AdminJob | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => adminApi.jobs().then(setJobs), []);
  useEffect(() => {
    load();
  }, [load]);

  const visible = useMemo(() => {
    const s = q.trim().toLowerCase();
    return (jobs ?? []).filter((j) => {
      if (filter === "active" && !BUSY.includes(j.state)) return false;
      if (filter === "done" && j.state !== "done") return false;
      if (filter === "error" && j.state !== "error") return false;
      if (filter === "orphan" && j.owner_id != null) return false;
      return !s || j.id.includes(s) || (j.filename ?? "").toLowerCase().includes(s) || (j.owner_email ?? "").includes(s);
    });
  }, [jobs, q, filter]);

  const total = (jobs ?? []).reduce((a, j) => a + j.size_bytes, 0);

  return (
    <>
      <PanelTitle
        title="Tất cả job"
        desc={jobs ? `${jobs.length} job · ${bytes(total)} trên đĩa` : "Đang tải…"}
        actions={
          <IconButton label="Làm mới" onClick={load}>
            <RefreshCw className="size-4" />
          </IconButton>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchBox value={q} onChange={setQ} placeholder="Tìm theo file, mã job, chủ sở hữu…" />
        <Segmented<Filter> value={filter} onChange={setFilter} options={[["all", "Tất cả"], ["active", "Đang chạy"], ["done", "Hoàn tất"], ["error", "Lỗi"], ["orphan", "Không chủ"]]} />
      </div>
      <Table head={["Clip", "Chủ sở hữu", "Trạng thái", "Dung lượng", "Tạo lúc", ""]} empty={jobs && !visible.length ? <p className="py-10 text-center text-sm text-muted">Không có job nào khớp.</p> : undefined}>
        {jobs === null
          ? [0, 1, 2].map((i) => (
              <tr key={i}>
                <td colSpan={6} className="px-4 py-3">
                  <div className="shimmer h-10 rounded-lg" />
                </td>
              </tr>
            ))
          : visible.map((j, i) => (
              <motion.tr key={j.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.015 }} className="transition hover:bg-surface-2/40">
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-3">
                    <video src={`${sourceUrl(j.id)}#t=1`} preload="metadata" muted className="h-10 w-16 shrink-0 rounded-md bg-black object-cover" />
                    <div className="min-w-0">
                      <p className="max-w-64 truncate font-semibold">{j.filename ?? j.id}</p>
                      <p className="font-mono text-[11px] text-muted">{j.id}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  {j.owner_email ? (
                    <>
                      <p className="font-medium">{j.owner_name}</p>
                      <p className="text-xs text-muted">{j.owner_email}</p>
                    </>
                  ) : (
                    <span className="text-xs text-muted italic">không có chủ</span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  <StateBadge state={(j.state ?? "unknown") as JobState} />
                  {j.state === "error" && j.error && (
                    <p className="mt-1 max-w-56 truncate font-mono text-[11px] text-rec" title={j.error}>
                      {j.error}
                    </p>
                  )}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs tabular">{bytes(j.size_bytes)}</td>
                <td className="px-4 py-2.5 text-muted" title={fmtDate(j.created_at)}>
                  {relTime(new Date(j.created_at * 1000))}
                </td>
                <td className="px-2 py-2.5 text-right whitespace-nowrap">
                  <IconButton label="Mở phòng biên tập" onClick={() => navigate(`#/jobs/${j.id}`)}>
                    <ExternalLink className="size-4" />
                  </IconButton>
                  <IconButton label="Xoá job" onClick={() => setDeleting(j)} disabled={BUSY.includes(j.state)} className="hover:text-rec">
                    <Trash className="size-4" />
                  </IconButton>
                </td>
              </motion.tr>
            ))}
      </Table>

      <Modal
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Xoá job?"
        description={
          <>
            Xoá vĩnh viễn <b className="text-ink">{deleting?.filename ?? deleting?.id}</b> ({deleting && bytes(deleting.size_bytes)}): video gốc, audio tách, bản lồng tiếng và mọi bản sửa.
          </>
        }
      >
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setDeleting(null)}>
            Huỷ
          </Button>
          <Button
            variant="danger"
            loading={busy}
            icon={<Trash className="size-4" />}
            onClick={async () => {
              setBusy(true);
              try {
                await api.deleteJob(deleting!.id);
                toast.success("Đã xoá job");
                setDeleting(null);
                load();
              } catch (e) {
                toast.error("Không xoá được", { description: (e as Error).message });
              } finally {
                setBusy(false);
              }
            }}
            data-autofocus
          >
            Xoá vĩnh viễn
          </Button>
        </div>
      </Modal>
    </>
  );
}
