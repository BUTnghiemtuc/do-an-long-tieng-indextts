import { Save } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { Toggle } from "../../components/form";
import { Button, Card } from "../../components/ui";
import { adminApi, type Settings } from "../../lib/api";
import { refreshAuth } from "../../lib/auth";
import { PanelTitle } from "./common";

function Row({ title, desc, children }: { title: string; desc: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="max-w-lg">
        <p className="font-semibold">{title}</p>
        <p className="text-sm text-muted">{desc}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function NumberInput({ value, onChange, min, max, unit }: { value: number; onChange: (v: number) => void; min: number; max: number; unit: string }) {
  return (
    <label className="flex h-10 items-center gap-2 rounded-xl border border-line-strong bg-surface px-3 focus-within:border-accent">
      <input type="number" min={min} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-20 bg-transparent text-right font-mono outline-none" />
      <span className="text-sm text-muted">{unit}</span>
    </label>
  );
}

export function SettingsTab() {
  const [saved, setSaved] = useState<Settings | null>(null);
  const [draft, setDraft] = useState<Settings | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    adminApi.settings().then((s) => {
      setSaved(s);
      setDraft(s);
    });
  }, []);
  if (!draft || !saved) return <div className="shimmer h-96 rounded-2xl" />;

  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setDraft({ ...draft, [k]: v });
  const changed = (Object.keys(draft) as (keyof Settings)[]).filter((k) => draft[k] !== saved[k]);

  return (
    <>
      <PanelTitle title="Cài đặt hệ thống" desc="Áp dụng ngay cho mọi người dùng, được ghi vào nhật ký." />
      <Card className="divide-y divide-line px-5">
        <Row title="Cho phép tự đăng ký" desc="Tắt khi demo trước hội đồng để chỉ tài khoản do quản trị viên tạo mới đăng nhập được.">
          <Toggle label="Cho phép tự đăng ký" checked={draft.allow_registration} onChange={(v) => set("allow_registration", v)} />
        </Row>
        <Row title="Dung lượng tối đa mỗi clip" desc="Chặn ngay từ header Content-Length và kiểm tra lại khi ghi file.">
          <NumberInput value={draft.max_upload_mb} onChange={(v) => set("max_upload_mb", v)} min={1} max={10000} unit="MB" />
        </Row>
        <Row title="Job chưa xong tối đa mỗi người" desc="Chỉ có một GPU nên job chạy lần lượt; giới hạn này tránh một người chiếm cả hàng đợi. Không áp dụng cho quản trị viên.">
          <NumberInput value={draft.max_active_jobs} onChange={(v) => set("max_active_jobs", v)} min={1} max={100} unit="job" />
        </Row>
        <Row title="Thời hạn phiên thường" desc="Khi không chọn “Ghi nhớ đăng nhập”.">
          <NumberInput value={draft.session_hours} onChange={(v) => set("session_hours", v)} min={1} max={720} unit="giờ" />
        </Row>
        <Row title="Thời hạn phiên “Ghi nhớ”" desc="Phiên dài hơn chỉ nên bật trên máy cá nhân.">
          <NumberInput value={draft.remember_days} onChange={(v) => set("remember_days", v)} min={1} max={365} unit="ngày" />
        </Row>
      </Card>
      <div className="sticky bottom-4 mt-5 flex items-center justify-end gap-3">
        {changed.length > 0 && <span className="rounded-full bg-surface px-3 py-1 text-sm text-muted shadow">{changed.length} thay đổi chưa lưu</span>}
        <Button variant="ghost" disabled={!changed.length} onClick={() => setDraft(saved)}>
          Hoàn tác
        </Button>
        <Button
          variant="primary"
          disabled={!changed.length}
          loading={busy}
          icon={<Save className="size-4" />}
          onClick={async () => {
            setBusy(true);
            try {
              const body = Object.fromEntries(changed.map((k) => [k, draft[k]])) as Partial<Settings>;
              const s = await adminApi.patchSettings(body);
              setSaved(s);
              setDraft(s);
              refreshAuth();
              toast.success("Đã lưu cài đặt");
            } catch (e) {
              toast.error("Không lưu được", { description: (e as Error).message });
            } finally {
              setBusy(false);
            }
          }}
        >
          Lưu cài đặt
        </Button>
      </div>
    </>
  );
}
