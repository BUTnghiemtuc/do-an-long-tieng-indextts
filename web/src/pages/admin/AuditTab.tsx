import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { IconButton } from "../../components/ui";
import { adminApi, type AuditEntry } from "../../lib/api";
import { fmtDate } from "../AccountPage";
import { ACTIONS, ActionBadge, PanelTitle, SearchBox, Table } from "./common";

const PAGE = 50;

function detailText(d: string | null): string {
  if (!d) return "";
  try {
    const o = JSON.parse(d);
    return Object.entries(o)
      .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
      .join(" · ");
  } catch {
    return d;
  }
}

export function AuditTab() {
  const [items, setItems] = useState<AuditEntry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [actions, setActions] = useState<string[]>([]);
  const [action, setAction] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);

  const load = () =>
    adminApi.audit({ limit: PAGE, offset: page * PAGE, action, q }).then((r) => {
      setItems(r.items);
      setTotal(r.total);
      setActions(r.actions);
    });

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0); // chờ gõ xong mới tìm
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, q, page]);

  const pages = Math.max(1, Math.ceil(total / PAGE));
  return (
    <>
      <PanelTitle
        title="Nhật ký hoạt động"
        desc="Mọi lần đăng nhập, thay đổi tài khoản, tạo/xoá job và đổi cài đặt đều được ghi lại."
        actions={
          <IconButton label="Làm mới" onClick={load}>
            <RefreshCw className="size-4" />
          </IconButton>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchBox
          value={q}
          onChange={(v) => {
            setQ(v);
            setPage(0);
          }}
          placeholder="Tìm theo email, đối tượng, IP…"
        />
        <select
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(0);
          }}
          className="h-9 rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-line-strong"
          aria-label="Lọc theo hành động"
        >
          <option value="">Mọi hành động</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {ACTIONS[a]?.label ?? a}
            </option>
          ))}
        </select>
        <span className="ml-auto text-sm text-muted">{total} bản ghi</span>
      </div>

      <Table head={["Thời gian", "Người thực hiện", "Hành động", "Đối tượng", "IP", "Chi tiết"]} empty={items && !items.length ? <p className="py-10 text-center text-sm text-muted">Chưa có bản ghi nào.</p> : undefined}>
        {(items ?? []).map((a) => (
          <tr key={a.id} className="hover:bg-surface-2/40">
            <td className="px-4 py-2.5 font-mono text-xs whitespace-nowrap text-muted">{fmtDate(a.ts)}</td>
            <td className="max-w-48 truncate px-4 py-2.5">{a.email ?? <span className="text-muted">—</span>}</td>
            <td className="px-4 py-2.5">
              <ActionBadge action={a.action} />
            </td>
            <td className="max-w-48 truncate px-4 py-2.5 font-mono text-xs">{a.target ?? ""}</td>
            <td className="px-4 py-2.5 font-mono text-xs text-muted">{a.ip}</td>
            <td className="max-w-64 truncate px-4 py-2.5 text-xs text-muted" title={detailText(a.detail)}>
              {detailText(a.detail)}
            </td>
          </tr>
        ))}
      </Table>

      <div className="mt-4 flex items-center justify-end gap-2 text-sm">
        <IconButton label="Trang trước" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
          <ChevronLeft className="size-4" />
        </IconButton>
        <span className="font-mono text-xs text-muted">
          {page + 1} / {pages}
        </span>
        <IconButton label="Trang sau" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
          <ChevronRight className="size-4" />
        </IconButton>
      </div>
    </>
  );
}
