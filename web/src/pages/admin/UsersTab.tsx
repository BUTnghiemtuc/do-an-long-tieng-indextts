import { motion } from "motion/react";
import { Ban, Check, CircleCheck, Copy, Crown, EllipsisVertical, KeyRound, LogOut, Mail, Trash, UserPlus, UserRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Menu, MenuItem, Modal, PasswordField, TextField } from "../../components/form";
import { Button, cx, IconButton, SpeakerAvatar } from "../../components/ui";
import { adminApi, type AdminUser, type Role } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { relTime } from "../../lib/format";
import { fmtDate } from "../AccountPage";
import { PanelTitle, SearchBox, Segmented, Table } from "./common";

type Filter = "all" | "admin" | "user" | "disabled";

function TempPassword({ email, password, onClose }: { email: string; password: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <Modal open onClose={onClose} title="Mật khẩu tạm" description={<>Gửi cho <b className="text-ink">{email}</b> qua kênh riêng. Mật khẩu chỉ hiện một lần; lần đăng nhập đầu người dùng phải đặt mật khẩu mới.</>}>
      <div className="flex items-center gap-2 rounded-2xl border border-dashed border-accent/60 bg-accent/8 p-4">
        <code className="flex-1 font-mono text-xl font-bold tracking-wider select-all">{password}</code>
        <Button
          size="sm"
          variant={copied ? "outline" : "primary"}
          icon={copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          onClick={async () => {
            await navigator.clipboard?.writeText(password).catch(() => {});
            setCopied(true);
          }}
          data-autofocus
        >
          {copied ? "Đã chép" : "Chép"}
        </Button>
      </div>
      <Button className="mt-5 w-full" onClick={onClose}>
        Xong
      </Button>
    </Modal>
  );
}

function CreateUser({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (email: string, temp: string | null) => void }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("user");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setEmail("");
      setName("");
      setRole("user");
      setPassword("");
      setError(null);
    }
  }, [open]);
  return (
    <Modal open={open} onClose={onClose} title="Thêm người dùng" description="Bỏ trống mật khẩu để hệ thống sinh mật khẩu tạm và buộc đổi ở lần đăng nhập đầu.">
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            const r = await adminApi.createUser({ email, name, role, password: password || undefined });
            onCreated(r.user.email, r.temp_password);
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <TextField label="Email" type="email" icon={<Mail />} value={email} onChange={(e) => setEmail(e.target.value)} />
        <TextField label="Tên hiển thị" icon={<UserRound />} value={name} onChange={(e) => setName(e.target.value)} />
        <div>
          <p className="mb-1.5 text-[13px] font-semibold">Vai trò</p>
          <Segmented<Role> value={role} onChange={setRole} options={[["user", "Người biên tập"], ["admin", "Quản trị viên"]]} />
        </div>
        <PasswordField label="Mật khẩu (tuỳ chọn)" autoComplete="new-password" icon={<KeyRound />} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="để trống = mật khẩu tạm" />
        {error && <p className="rounded-xl bg-rec/8 px-3 py-2 text-sm font-medium text-rec">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" variant="primary" loading={busy} disabled={!email} icon={<UserPlus className="size-4" />}>
            Tạo tài khoản
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ConfirmDelete({ user, onClose, onDone }: { user: AdminUser | null; onClose: () => void; onDone: () => void }) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => setTyped(""), [user]);
  return (
    <Modal
      open={!!user}
      onClose={onClose}
      title="Xoá người dùng?"
      description={
        <>
          Tài khoản <b className="text-ink">{user?.email}</b> và mọi phiên đăng nhập sẽ bị xoá vĩnh viễn. {user?.job_count ? `${user.job_count} job của người này được giữ lại (không còn chủ sở hữu, chỉ quản trị viên thấy).` : ""}
        </>
      }
    >
      <TextField label="Gõ lại email để xác nhận" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={user?.email} />
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Huỷ
        </Button>
        <Button
          variant="danger"
          loading={busy}
          disabled={typed.trim().toLowerCase() !== user?.email}
          icon={<Trash className="size-4" />}
          onClick={async () => {
            setBusy(true);
            try {
              await adminApi.deleteUser(user!.id);
              toast.success(`Đã xoá ${user!.email}`);
              onDone();
            } catch (e) {
              toast.error("Không xoá được", { description: (e as Error).message });
            } finally {
              setBusy(false);
            }
          }}
        >
          Xoá vĩnh viễn
        </Button>
      </div>
    </Modal>
  );
}

export function UsersTab() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [creating, setCreating] = useState(false);
  const [temp, setTemp] = useState<{ email: string; password: string } | null>(null);
  const [deleting, setDeleting] = useState<AdminUser | null>(null);

  const load = useCallback(() => adminApi.users().then(setUsers), []);
  useEffect(() => {
    load();
  }, [load]);

  const visible = useMemo(() => {
    const s = q.trim().toLowerCase();
    return (users ?? []).filter((u) => {
      if (filter === "admin" && u.role !== "admin") return false;
      if (filter === "user" && u.role !== "user") return false;
      if (filter === "disabled" && u.active) return false;
      return !s || u.email.includes(s) || u.name.toLowerCase().includes(s);
    });
  }, [users, q, filter]);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      toast.success(ok);
      load();
    } catch (e) {
      toast.error("Không thực hiện được", { description: (e as Error).message });
    }
  };

  return (
    <>
      <PanelTitle
        title="Người dùng"
        desc={users ? `${users.length} tài khoản · ${users.filter((u) => u.role === "admin").length} quản trị viên` : "Đang tải…"}
        actions={
          <Button variant="primary" size="sm" icon={<UserPlus className="size-4" />} onClick={() => setCreating(true)}>
            Thêm người dùng
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchBox value={q} onChange={setQ} placeholder="Tìm theo tên hoặc email…" />
        <Segmented<Filter> value={filter} onChange={setFilter} options={[["all", "Tất cả"], ["admin", "Quản trị"], ["user", "Biên tập"], ["disabled", "Đã khoá"]]} />
      </div>

      <Table
        head={["Người dùng", "Vai trò", "Trạng thái", "Job", "Phiên", "Đăng nhập gần nhất", ""]}
        empty={users && visible.length === 0 ? <p className="py-10 text-center text-sm text-muted">Không có người dùng nào khớp.</p> : undefined}
      >
        {users === null
          ? [0, 1, 2].map((i) => (
              <tr key={i}>
                <td colSpan={7} className="px-4 py-3">
                  <div className="shimmer h-9 rounded-lg" />
                </td>
              </tr>
            ))
          : visible.map((u, i) => {
              const self = u.id === me?.id;
              return (
                <motion.tr key={u.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.02 }} className={cx("transition hover:bg-surface-2/40", !u.active && "opacity-60")}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <SpeakerAvatar name={u.name} color={u.role === "admin" ? "var(--color-accent)" : "var(--color-spk-3)"} size={34} />
                      <div className="min-w-0">
                        <p className="truncate font-semibold">
                          {u.name} {self && <span className="text-xs font-medium text-muted">(bạn)</span>}
                        </p>
                        <p className="truncate text-xs text-muted">{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {u.role === "admin" ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[11px] font-bold text-accent-strong">
                        <Crown className="size-3" /> Quản trị
                      </span>
                    ) : (
                      <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] font-bold text-muted">Biên tập</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {!u.active ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-rec">
                        <Ban className="size-3.5" /> Đã khoá
                      </span>
                    ) : u.must_change_password ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-warn">
                        <KeyRound className="size-3.5" /> Chờ đổi mật khẩu
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-ok">
                        <CircleCheck className="size-3.5" /> Hoạt động
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono tabular">{u.job_count}</td>
                  <td className="px-4 py-3 font-mono tabular">{u.session_count}</td>
                  <td className="px-4 py-3 text-muted" title={fmtDate(u.last_login_at)}>
                    {u.last_login_at ? relTime(new Date(u.last_login_at * 1000)) : "chưa đăng nhập"}
                  </td>
                  <td className="px-2 py-3 text-right">
                    <Menu
                      trigger={(_, toggle) => (
                        <IconButton label="Thao tác" onClick={toggle}>
                          <EllipsisVertical className="size-4" />
                        </IconButton>
                      )}
                    >
                      {(close) => (
                        <>
                          <MenuItem
                            icon={<Crown />}
                            disabled={self}
                            onClick={() => (close(), act(() => adminApi.patchUser(u.id, { role: u.role === "admin" ? "user" : "admin" }), u.role === "admin" ? "Đã chuyển thành người biên tập" : "Đã cấp quyền quản trị"))}
                          >
                            {u.role === "admin" ? "Hạ xuống người biên tập" : "Cấp quyền quản trị"}
                          </MenuItem>
                          <MenuItem
                            icon={<KeyRound />}
                            onClick={async () => {
                              close();
                              try {
                                const r = await adminApi.resetPassword(u.id);
                                setTemp({ email: u.email, password: r.temp_password });
                                load();
                              } catch (e) {
                                toast.error("Không đặt lại được", { description: (e as Error).message });
                              }
                            }}
                          >
                            Cấp mật khẩu tạm
                          </MenuItem>
                          <MenuItem icon={<LogOut />} disabled={!u.session_count} onClick={() => (close(), act(() => adminApi.kick(u.id), `Đã đăng xuất ${u.email} khỏi mọi thiết bị`))}>
                            Buộc đăng xuất mọi thiết bị
                          </MenuItem>
                          <MenuItem icon={u.active ? <Ban /> : <CircleCheck />} disabled={self} onClick={() => (close(), act(() => adminApi.patchUser(u.id, { active: !u.active }), u.active ? "Đã khoá tài khoản" : "Đã mở khoá tài khoản"))}>
                            {u.active ? "Khoá tài khoản" : "Mở khoá tài khoản"}
                          </MenuItem>
                          <div className="my-1 border-t border-line" />
                          <MenuItem icon={<Trash />} danger disabled={self} onClick={() => (close(), setDeleting(u))}>
                            Xoá người dùng
                          </MenuItem>
                        </>
                      )}
                    </Menu>
                  </td>
                </motion.tr>
              );
            })}
      </Table>

      <CreateUser
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(email, tp) => {
          setCreating(false);
          toast.success(`Đã tạo ${email}`);
          if (tp) setTemp({ email, password: tp });
          load();
        }}
      />
      {temp && <TempPassword email={temp.email} password={temp.password} onClose={() => setTemp(null)} />}
      <ConfirmDelete
        user={deleting}
        onClose={() => setDeleting(null)}
        onDone={() => {
          setDeleting(null);
          load();
        }}
      />
    </>
  );
}
