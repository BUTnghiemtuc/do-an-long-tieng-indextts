import { motion } from "motion/react";
import {
  AudioLines,
  AudioWaveform,
  Captions,
  Film,
  Languages,
  Mic,
  RefreshCw,
  ScanFace,
  Scissors,
  Timer,
  Trash,
  Users,
  Wand2,
} from "lucide-react";
import { toast } from "sonner";
import { Modal } from "../components/form";
import { useEffect, useRef, useState } from "react";
import { Dropzone } from "../components/Dropzone";
import { HeroVisual } from "../components/HeroVisual";
import { Button, Card, IconButton, StateBadge } from "../components/ui";
import { useAuth } from "../lib/auth";
import { api, BUSY, sourceUrl, STEPS, type JobSummary, type StepName } from "../lib/api";
import { jobDate, relTime, STEP_INFO } from "../lib/format";
import { navigate } from "../lib/router";

const STEP_ICON: Record<StepName, typeof Film> = {
  extract: Film,
  separate: AudioWaveform,
  diarize: Users,
  transcribe: Captions,
  translate: Languages,
  synthesize: Mic,
  align: Timer,
  mix: AudioLines,
};

const FEATURES = [
  { icon: ScanFace, title: "Mỗi nhân vật một giọng", text: "Giọng mẫu lấy từ chính câu thoại gốc, IndexTTS giữ âm sắc và cảm xúc từng câu." },
  { icon: Timer, title: "Khớp khẩu hình thời gian", text: "Dịch theo ngân sách âm tiết, rồi co giãn ±10% và mượn khoảng lặng để vừa khít." },
  { icon: RefreshCw, title: "Sửa một câu, sinh lại một câu", text: "Cache theo từng câu: chỉnh bản dịch xong chỉ câu đó được tạo lại trong vài giây." },
  { icon: Scissors, title: "Nhạc nền nguyên vẹn", text: "Demucs tách giọng khỏi nhạc & hiệu ứng, bản lồng tiếng được trộn lại ở −20 LUFS." },
];

const ease = [0.2, 0.8, 0.2, 1] as const;

function JobCard({ job, index, onDelete }: { job: JobSummary; index: number; onDelete: (j: JobSummary) => void }) {
  const ref = useRef<HTMLVideoElement>(null);
  const date = jobDate(job.id);
  return (
    <Card
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.04 * index, duration: 0.5, ease }}
      whileHover={{ y: -4 }}
      onHoverStart={() => ref.current?.play().catch(() => {})}
      onHoverEnd={() => ref.current?.pause()}
      onClick={() => navigate(`#/jobs/${job.id}`)}
      className="group cursor-pointer overflow-hidden"
      role="link"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && navigate(`#/jobs/${job.id}`)}
    >
      <div className="relative aspect-video overflow-hidden bg-black">
        <video ref={ref} src={`${sourceUrl(job.id)}#t=1`} muted loop playsInline preload="metadata" className="size-full object-cover opacity-90 transition duration-500 group-hover:scale-105 group-hover:opacity-100" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent" />
        <StateBadge state={job.state} className="absolute top-3 left-3 bg-black/55! text-white! backdrop-blur" />
        <span className="absolute right-3 bottom-3 rounded-md bg-black/55 px-2 py-0.5 font-mono text-[11px] text-white/80 backdrop-blur">EN → VI</span>
        {!BUSY.includes(job.state) && (
          <IconButton
            label="Xoá job"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(job);
            }}
            className="absolute top-2.5 right-2.5 size-8 bg-black/45 text-white/80 opacity-0 backdrop-blur group-hover:opacity-100 hover:bg-rec! hover:text-white focus-visible:opacity-100"
          >
            <Trash className="size-3.5" />
          </IconButton>
        )}
      </div>
      <div className="p-4">
        <p className="truncate font-semibold">{job.filename || job.id}</p>
        <p className="mt-0.5 text-xs text-muted">
          {relTime(date)} · <span className="font-mono">{job.id.slice(-6)}</span>
        </p>
      </div>
    </Card>
  );
}

export function Home() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [offline, setOffline] = useState(false);
  const [deleting, setDeleting] = useState<JobSummary | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .jobs()
      .then(setJobs)
      .catch(() => {
        setOffline(true);
        setJobs([]);
      });
  }, []);

  return (
    <main>
      {/* ------------------------------------------------ hero */}
      <section className="relative overflow-hidden">
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
          <div className="absolute -top-40 -left-32 size-[520px] rounded-full bg-accent/20 blur-[100px]" style={{ animation: "aurora 18s ease-in-out infinite" }} />
          <div className="absolute top-20 right-[-10%] size-[460px] rounded-full bg-rec/12 blur-[110px]" style={{ animation: "aurora 22s ease-in-out infinite reverse" }} />
          <div className="absolute bottom-[-30%] left-1/3 size-[420px] rounded-full bg-spk-1/15 blur-[110px]" style={{ animation: "aurora 26s ease-in-out infinite" }} />
          <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--color-line)_1px,transparent_1px),linear-gradient(to_bottom,var(--color-line)_1px,transparent_1px)] [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_70%)] bg-[size:56px_56px] opacity-50" />
        </div>

        <div className="mx-auto grid max-w-[1440px] items-center gap-10 px-4 pt-12 pb-16 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:pt-20">
          <div>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/70 px-3 py-1.5 text-xs font-semibold text-muted backdrop-blur">
              <Wand2 className="size-3.5 text-accent-strong" /> IndexTTS 2.5 · finetune tiếng Việt
            </motion.div>
            <motion.h1
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease, delay: 0.05 }}
              className="mt-5 text-[40px] leading-[1.05] font-extrabold tracking-[-0.035em] text-balance sm:text-6xl xl:text-7xl"
            >
              Lồng tiếng phim sang <span className="text-gradient">tiếng Việt</span>, giữ nguyên giọng nhân vật.
            </motion.h1>
            <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease, delay: 0.15 }} className="mt-5 max-w-xl text-lg text-muted text-pretty">
              Tải lên một clip tiếng Anh. vidub tách giọng, nhận diện từng nhân vật, dịch theo ngữ cảnh rồi sinh giọng Việt khớp thời lượng, nhạc nền giữ nguyên.
            </motion.p>
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease, delay: 0.25 }} className="mt-8 max-w-xl">
              <Dropzone />
            </motion.div>
          </div>
          <HeroVisual />
        </div>

        {/* Dải phim chạy ngang: 8 bước của pipeline */}
        <div className="border-y border-line bg-surface/60 backdrop-blur">
          <div className="film-perf" />
          <div className="overflow-hidden py-3">
            <div className="flex w-max animate-marquee gap-3 hover:[animation-play-state:paused]">
              {[...STEPS, ...STEPS].map((s, k) => {
                const Icon = STEP_ICON[s];
                return (
                  <span key={k} className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-3.5 py-2 text-sm">
                    <span className="font-mono text-[11px] text-muted">{String((k % 8) + 1).padStart(2, "0")}</span>
                    <Icon className="size-4 text-accent-strong" />
                    <span className="font-semibold">{STEP_INFO[s].label}</span>
                    <span className="text-muted">· {STEP_INFO[s].tool}</span>
                  </span>
                );
              })}
            </div>
          </div>
          <div className="film-perf" />
        </div>
      </section>

      {/* ------------------------------------------------ dự án */}
      <section className="mx-auto max-w-[1440px] px-4 py-14 sm:px-6">
        <div className="mb-6 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-extrabold tracking-tight">Dự án của {user?.name ?? "bạn"}</h2>
            <p className="text-sm text-muted">Mở một clip để biên tập bản dịch, đổi giọng mẫu, nghe so sánh.</p>
          </div>
          {jobs && jobs.length > 0 && <span className="text-sm font-semibold text-muted">{jobs.length} clip</span>}
        </div>

        {jobs === null ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="overflow-hidden rounded-2xl border border-line">
                <div className="shimmer aspect-video" />
                <div className="space-y-2 p-4">
                  <div className="shimmer h-4 w-2/3 rounded" />
                  <div className="shimmer h-3 w-1/3 rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="grid place-items-center rounded-3xl border border-dashed border-line-strong px-6 py-16 text-center">
            <Film className="size-10 text-muted" />
            <p className="mt-3 font-semibold">{offline ? "Chưa kết nối được máy chủ" : "Chưa có dự án nào"}</p>
            <p className="mt-1 max-w-md text-sm text-muted">
              {offline ? (
                <>
                  Chạy <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">uvicorn server.app:app</code> rồi tải lại trang.
                </>
              ) : (
                "Kéo một clip phim vào ô phía trên để bắt đầu."
              )}
            </p>
          </div>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {jobs.map((j, i) => (
              <JobCard key={j.id} job={j} index={i} onDelete={setDeleting} />
            ))}
          </div>
        )}
      </section>

      {/* ------------------------------------------------ tính năng */}
      <section className="mx-auto max-w-[1440px] px-4 pb-20 sm:px-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f, i) => (
            <Card
              key={f.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ delay: i * 0.08, duration: 0.6, ease }}
              className="p-5"
            >
              <span className="grid size-10 place-items-center rounded-xl bg-accent/12 text-accent-strong">
                <f.icon className="size-5" />
              </span>
              <h3 className="mt-4 font-bold">{f.title}</h3>
              <p className="mt-1.5 text-sm text-muted">{f.text}</p>
            </Card>
          ))}
        </div>
      </section>
      <Modal
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Xoá dự án?"
        description={<>Xoá vĩnh viễn <b className="text-ink">{deleting?.filename ?? deleting?.id}</b> cùng video gốc, bản lồng tiếng và mọi bản sửa. Không hoàn tác được.</>}
      >
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setDeleting(null)}>
            Huỷ
          </Button>
          <Button
            variant="danger"
            loading={busy}
            data-autofocus
            icon={<Trash className="size-4" />}
            onClick={async () => {
              setBusy(true);
              try {
                await api.deleteJob(deleting!.id);
                setJobs((js) => js?.filter((j) => j.id !== deleting!.id) ?? null);
                toast.success("Đã xoá dự án");
                setDeleting(null);
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
    </main>
  );
}
