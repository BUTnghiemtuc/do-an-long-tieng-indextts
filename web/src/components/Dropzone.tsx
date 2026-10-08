import { AnimatePresence, motion } from "motion/react";
import { Captions, FileVideo, Languages, Sparkles, UploadCloud, X } from "lucide-react";
import { useRef, useState, type DragEvent, type ReactNode } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { LANGS } from "../lib/format";
import { navigate } from "../lib/router";
import { Button, cx } from "./ui";

const SRC_LANGS = ["en", "zh"] as const;

function sizeOf(f: File) {
  return f.size > 1e6 ? `${(f.size / 1e6).toFixed(1)} MB` : `${Math.round(f.size / 1e3)} KB`;
}

export function Dropzone() {
  const { user } = useAuth();
  const [video, setVideo] = useState<File | null>(null);
  const [srt, setSrt] = useState<File | null>(null);
  const [lang, setLang] = useState<string>("en");
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const videoInput = useRef<HTMLInputElement>(null);
  const srtInput = useRef<HTMLInputElement>(null);

  const take = (files: FileList | File[]) => {
    const maxMb = user?.limits.max_upload_mb ?? Infinity;
    for (const f of Array.from(files)) {
      if (f.size > maxMb * 2 ** 20) {
        toast.error(`${f.name} quá lớn`, { description: `Tối đa ${maxMb} MB mỗi clip.` });
        continue;
      }
      if (/\.srt$/i.test(f.name)) setSrt(f);
      else if (/^(video|audio)\//.test(f.type) || /\.(mp4|mkv|mov|webm|wav|mp3)$/i.test(f.name)) setVideo(f);
      else toast.error(`Không nhận file ${f.name}`, { description: "Chỉ nhận video/audio và phụ đề .srt" });
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    take(e.dataTransfer.files);
  };

  const submit = async () => {
    if (!video) return;
    setBusy(true);
    const form = new FormData();
    form.append("video", video);
    if (srt) form.append("subtitles", srt);
    form.append("src_lang", lang);
    try {
      const { id } = await api.create(form);
      toast.success("Đã nhận clip, bắt đầu lồng tiếng", { description: video.name });
      navigate(`#/jobs/${id}`);
    } catch (e) {
      toast.error("Tải lên thất bại", { description: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={(e) => e.currentTarget.contains(e.relatedTarget as Node) || setOver(false)}
      onDrop={onDrop}
      className={cx(
        "relative rounded-3xl p-5 transition-shadow sm:p-6",
        over ? "ants-border shadow-[0_0_60px_-15px_var(--color-accent)]" : "border border-line bg-surface",
      )}
    >
      <input ref={videoInput} type="file" accept="video/*,audio/*" hidden onChange={(e) => e.target.files && take(e.target.files)} />
      <input ref={srtInput} type="file" accept=".srt" hidden onChange={(e) => e.target.files && take(e.target.files)} />

      <button
        onClick={() => videoInput.current?.click()}
        className="group flex w-full flex-col items-center gap-3 rounded-2xl border border-dashed border-line-strong bg-surface-2/50 px-4 py-8 text-center transition hover:border-accent hover:bg-accent/5"
      >
        <motion.span
          animate={over ? { y: -6, scale: 1.1 } : { y: 0, scale: 1 }}
          className="grid size-14 place-items-center rounded-2xl bg-accent/15 text-accent-strong transition group-hover:scale-105"
        >
          <UploadCloud className="size-7" />
        </motion.span>
        <span className="text-base font-bold">{over ? "Thả vào đây" : "Kéo thả clip phim vào đây"}</span>
        <span className="text-sm text-muted">
          hoặc <span className="font-semibold text-accent-strong underline-offset-4 group-hover:underline">chọn file</span> · MP4, MKV,
          MOV · 1–5 phút · tối đa {user?.limits.max_upload_mb ?? 500} MB
        </span>
      </button>

      <div className="mt-4 space-y-2">
        <AnimatePresence initial={false}>
          {[
            video && { f: video, icon: <FileVideo className="size-4" />, clear: () => setVideo(null), tag: "Video" },
            srt && { f: srt, icon: <Captions className="size-4" />, clear: () => setSrt(null), tag: "Phụ đề gốc" },
          ]
            .filter(Boolean)
            .map((x) => {
              const it = x as { f: File; icon: ReactNode; clear: () => void; tag: string };
              return (
                <motion.div
                  key={it.tag}
                  layout
                  initial={{ opacity: 0, y: -8, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ type: "spring", stiffness: 420, damping: 30 }}
                  className="flex items-center gap-3 rounded-xl border border-line bg-surface-2/60 px-3 py-2"
                >
                  <span className="grid size-8 place-items-center rounded-lg bg-surface text-accent-strong">{it.icon}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold">{it.f.name}</span>
                    <span className="text-xs text-muted">
                      {it.tag} · {sizeOf(it.f)}
                    </span>
                  </span>
                  <button onClick={it.clear} className="rounded-lg p-1.5 text-muted hover:bg-surface hover:text-ink" aria-label="Bỏ file">
                    <X className="size-4" />
                  </button>
                </motion.div>
              );
            })}
        </AnimatePresence>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {!srt && (
          <button onClick={() => srtInput.current?.click()} className="inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink">
            <Captions className="size-4" /> Thêm phụ đề gốc (.srt)
          </button>
        )}
        <div className="ml-auto flex items-center gap-2">
          <Languages className="size-4 text-muted" />
          <div className="relative flex rounded-xl bg-surface-2 p-1 text-[13px] font-semibold">
            {SRC_LANGS.map((l) => (
              <button key={l} onClick={() => setLang(l)} className={cx("relative rounded-lg px-3 py-1.5 transition", lang === l ? "text-ink" : "text-muted")}>
                {lang === l && (
                  <motion.span layoutId="lang-pill" className="absolute inset-0 rounded-lg bg-surface shadow ring-1 ring-line" transition={{ type: "spring", stiffness: 500, damping: 35 }} />
                )}
                <span className="relative">{LANGS[l]}</span>
              </button>
            ))}
          </div>
          <span className="text-sm text-muted">→ Tiếng Việt</span>
        </div>
      </div>

      <Button variant="primary" size="lg" className="mt-5 w-full" disabled={!video} loading={busy} icon={<Sparkles className="size-5" />} onClick={submit}>
        Bắt đầu lồng tiếng
      </Button>
    </div>
  );
}
