import NumberFlow from "@number-flow/react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, Captions, ChevronDown, Download, Gauge, History, Search, Sparkles, TriangleAlert, Users, Wand2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { ComparePlayer } from "../components/ComparePlayer";
import { Header } from "../components/Header";
import { PipelineStepper } from "../components/PipelineStepper";
import { SegmentCard, type Draft } from "../components/SegmentCard";
import { SpeakerPanel } from "../components/SpeakerPanel";
import { Button, cx, SpeakerAvatar, StateBadge } from "../components/ui";
import { WaveTimeline } from "../components/WaveTimeline";
import { useJob } from "../hooks/useJob";
import { PlayerContext, usePlayerState } from "../hooks/usePlayer";
import { api, fileUrl, isBusy, sourceUrl, STEPS, type Job, type Segment, type StepName } from "../lib/api";
import { secs, STEP_INFO, tc } from "../lib/format";
import { navigate } from "../lib/router";

type Filter = "all" | "warn" | "edited" | `spk:${string}`;

function Stat({ label, value, suffix, decimals = 0, tone, icon }: { label: string; value: number | null; suffix?: string; decimals?: number; tone?: string; icon: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3">
      <span className="grid size-9 place-items-center rounded-xl bg-surface-2 text-muted">{icon}</span>
      <div className="min-w-0">
        <p className={cx("font-mono text-lg leading-none font-bold tabular", tone)}>
          {value == null ? "–" : <NumberFlow value={value} suffix={suffix} format={{ maximumFractionDigits: decimals, minimumFractionDigits: decimals }} />}
        </p>
        <p className="mt-1 truncate text-[11px] font-medium text-muted">{label}</p>
      </div>
    </div>
  );
}

function RerunMenu({ disabled, onRun }: { disabled: boolean; onRun: (step: StepName, force: boolean) => void }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<StepName>("translate");
  const [force, setForce] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current?.contains(e.target as Node) || setOpen(false);
    addEventListener("mousedown", close);
    return () => removeEventListener("mousedown", close);
  }, [open]);
  return (
    <div ref={ref} className="relative">
      <Button size="sm" variant="outline" disabled={disabled} icon={<History className="size-3.5" />} onClick={() => setOpen((v) => !v)}>
        Chạy lại <ChevronDown className={cx("size-3.5 transition", open && "rotate-180")} />
      </Button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 z-50 mt-2 w-72 origin-top-right rounded-2xl border border-line bg-surface p-3 shadow-2xl shadow-black/15"
          >
            <p className="mb-2 text-xs font-semibold text-muted">Chạy lại từ bước</p>
            <div className="grid max-h-72 gap-1 overflow-auto">
              {STEPS.map((s, i) => (
                <button key={s} onClick={() => setStep(s)} className={cx("flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm transition", step === s ? "bg-accent/15 font-semibold text-accent-strong" : "hover:bg-surface-2")}>
                  <span className="font-mono text-[11px] text-muted">{i + 1}</span> {STEP_INFO[s].label}
                  <span className="ml-auto text-[11px] text-muted">{STEP_INFO[s].tool}</span>
                </button>
              ))}
            </div>
            <label className="mt-3 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
              Bỏ qua cache (force)
            </label>
            <Button
              size="sm"
              variant="primary"
              className="mt-3 w-full"
              onClick={() => {
                setOpen(false);
                onRun(step, force);
              }}
            >
              Chạy từ “{STEP_INFO[step].label}”
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Studio({ job, setJob, refresh, watch, disclaimer }: { job: Job; setJob: (j: Job) => void; refresh: () => Promise<Job | null>; watch: () => void; disclaimer?: string }) {
  const id = job.id;
  const p = job.project;
  const busy = isBusy(job.status);
  const mixVersion = p.steps.mix?.finished_at ?? undefined;
  const dubUrl = fileUrl(id, p.outputs.video, mixVersion);
  const player = usePlayerState(!!dubUrl);

  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [selected, setSelected] = useState<number | undefined>();
  const [tab, setTab] = useState<"segments" | "speakers">("segments");
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [follow, setFollow] = useState(true);
  const [applying, setApplying] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const spkIds = useMemo(() => Object.keys(p.speakers).sort(), [p.speakers]);
  const speakerIndex = useCallback((spk: string) => Math.max(0, spkIds.indexOf(spk)), [spkIds]);
  const color = useCallback((spk: string) => `var(--color-spk-${speakerIndex(spk) % 6})`, [speakerIndex]);
  const speakerName = useCallback((spk: string) => p.speakers[spk]?.name ?? spk, [p.speakers]);

  const dirtyIds = useMemo(
    () =>
      Object.entries(drafts)
        .filter(([sid, d]) => {
          const s = p.segments.find((x) => x.id === +sid);
          return s && ((d.vi_text != null && d.vi_text.trim() !== s.vi_text) || (d.speaker != null && d.speaker !== s.speaker));
        })
        .map(([sid]) => +sid),
    [drafts, p.segments],
  );

  const active = useMemo(() => p.segments.find((s) => player.time >= s.start && player.time < s.end), [p.segments, player.time]);
  const viText = useCallback((s: Segment) => drafts[s.id]?.vi_text ?? s.vi_text, [drafts]);

  // Cuộn danh sách theo đầu phát.
  useEffect(() => {
    if (!follow || !active || !player.playing || tab !== "segments") return;
    listRef.current?.querySelector(`[data-seg="${active.id}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [active, follow, player.playing, tab]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return p.segments.filter((s) => {
      if (filter === "warn" && !s.warnings.length) return false;
      if (filter === "edited" && !s.vi_locked && !dirtyIds.includes(s.id)) return false;
      if (filter.startsWith("spk:") && s.speaker !== filter.slice(4)) return false;
      return !q || s.src_text.toLowerCase().includes(q) || viText(s).toLowerCase().includes(q);
    });
  }, [p.segments, filter, query, dirtyIds, viText]);

  const fail = (title: string) => (e: unknown) => toast.error(title, { description: (e as Error).message });

  const saveDrafts = useCallback(async () => {
    let last: Job | null = null;
    for (const sid of dirtyIds) {
      const d = drafts[sid];
      last = await api.patchSegment(id, sid, { vi_text: d.vi_text, speaker: d.speaker });
    }
    if (last) setJob(last);
    setDrafts({});
  }, [dirtyIds, drafts, id, setJob]);

  const { seek, playRange } = player;
  const onSelect = useCallback(
    (s: Segment) => {
      setSelected(s.id);
      seek(s.start);
    },
    [seek],
  );
  const onDraft = useCallback((sid: number, d: Draft) => setDrafts((x) => ({ ...x, [sid]: d })), []);
  const onPlay = useCallback(
    (s: Segment, mode: "src" | "dub") => {
      setSelected(s.id);
      playRange(s.start, s.end, mode);
    },
    [playRange],
  );

  const onRegenerate = useCallback(
    async (s: Segment) => {
      try {
        const d = drafts[s.id];
        if (d) {
          setJob(await api.patchSegment(id, s.id, { vi_text: d.vi_text, speaker: d.speaker }));
          setDrafts(({ [s.id]: _, ...rest }) => rest);
        }
        await api.regenerate(id, s.id);
        toast.success(`Đang tạo lại câu #${s.id}`, { description: "Chỉ câu này được sinh giọng và trộn lại." });
        await refresh();
        watch();
      } catch (e) {
        fail("Không tạo lại được")(e);
      }
    },
    [drafts, id, refresh, setJob, watch],
  );

  const onUseTimbre = useCallback(
    async (s: Segment) => {
      try {
        setJob(await api.patchSpeaker(id, s.speaker, { timbre_from_segment: s.id }));
        toast.success(`Đã đổi giọng mẫu của ${speakerName(s.speaker)}`, { description: `Lấy từ câu #${s.id}. Bấm “Áp dụng thay đổi” để sinh lại.` });
      } catch (e) {
        fail("Không đổi được giọng mẫu")(e);
      }
    },
    [id, setJob, speakerName],
  );

  const onUnlock = useCallback(
    async (s: Segment) => {
      try {
        setJob(await api.patchSegment(id, s.id, { unlock: true }));
        setDrafts(({ [s.id]: _, ...rest }) => rest);
        toast(`Đã mở khoá câu #${s.id}`, { description: "Câu sẽ được LLM dịch lại khi áp dụng thay đổi." });
      } catch (e) {
        fail("Không mở khoá được")(e);
      }
    },
    [id, setJob],
  );

  const apply = async () => {
    setApplying(true);
    try {
      await saveDrafts();
      await api.render(id);
      toast.success("Đang áp dụng thay đổi", { description: "Dịch câu mới, sinh lại câu đã sửa, trộn lại video." });
      await refresh();
      watch();
    } catch (e) {
      fail("Không áp dụng được")(e);
    } finally {
      setApplying(false);
    }
  };

  const rerun = async (step: StepName, force: boolean) => {
    try {
      await api.rerun(id, step, force);
      toast.success(`Chạy lại từ “${STEP_INFO[step].label}”`);
      await refresh();
      watch();
    } catch (e) {
      fail("Không chạy lại được")(e);
    }
  };

  const go = (dir: 1 | -1) => {
    const segs = p.segments;
    if (!segs.length) return;
    const cur = segs.findIndex((s) => s.id === (selected ?? active?.id));
    const next = segs[Math.min(segs.length - 1, Math.max(0, cur < 0 ? 0 : cur + dir))];
    onSelect(next);
    listRef.current?.querySelector(`[data-seg="${next.id}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };

  // Phím tắt (không áp dụng khi đang gõ).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input,textarea,select,[contenteditable]")) {
        if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && t.tagName === "TEXTAREA" && selected != null) {
          e.preventDefault();
          const s = p.segments.find((x) => x.id === selected);
          if (s) onRegenerate(s);
        }
        return;
      }
      if (e.code === "Space") {
        e.preventDefault();
        player.toggle();
      } else if (e.key === "a" || e.key === "A") player.setMode(player.mode === "dub" ? "src" : "dub");
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  });

  // Chặn rời trang khi còn sửa chưa lưu.
  useEffect(() => {
    if (!dirtyIds.length) return;
    const h = (e: BeforeUnloadEvent) => e.preventDefault();
    addEventListener("beforeunload", h);
    return () => removeEventListener("beforeunload", h);
  }, [dirtyIds.length]);

  const withRatio = p.segments.filter((s) => s.duration_ratio != null);
  const within = withRatio.length ? (100 * withRatio.filter((s) => Math.abs(s.duration_ratio! - 1) <= 0.1).length) / withRatio.length : null;
  const warnCount = p.segments.filter((s) => s.warnings.length).length;
  const editedCount = p.segments.filter((s) => s.vi_locked).length;

  return (
    <PlayerContext.Provider value={player}>
      <Header>
        <button onClick={() => navigate("#/")} className="hidden items-center gap-1 rounded-lg px-2 py-1 text-sm text-muted hover:bg-surface-2 hover:text-ink sm:inline-flex">
          <ArrowLeft className="size-4" /> Dự án
        </button>
        <span className="hidden text-line-strong sm:inline">/</span>
        <h1 className="truncate text-sm font-bold sm:text-base">{p.clip_id}</h1>
        <StateBadge state={job.status.state} className="shrink-0" />
      </Header>

      <main className="mx-auto max-w-[1440px] space-y-4 px-4 py-5 sm:px-6">
        {/* Thanh hành động */}
        <div className="flex flex-wrap items-center gap-2">
          <p className="mr-auto text-sm text-muted">
            {p.src_lang.toUpperCase()} → VI · {tc(p.duration ?? 0, 0)} · {p.segments.length} câu · {spkIds.length} nhân vật
          </p>
          <RerunMenu disabled={busy} onRun={rerun} />
          {p.outputs.srt_vi && (
            <a href={fileUrl(id, p.outputs.srt_vi, mixVersion)} download className="inline-flex h-8 items-center gap-1.5 rounded-xl border border-line-strong bg-surface px-3 text-[13px] font-semibold hover:bg-surface-2">
              <Captions className="size-3.5" /> SRT
            </a>
          )}
          {p.outputs.video && (
            <a href={dubUrl} download className="inline-flex h-8 items-center gap-1.5 rounded-xl border border-line-strong bg-surface px-3 text-[13px] font-semibold hover:bg-surface-2">
              <Download className="size-3.5" /> MP4
            </a>
          )}
          <Button size="sm" variant="primary" disabled={busy} loading={applying} icon={<Wand2 className="size-3.5" />} onClick={apply}>
            Áp dụng thay đổi
            <AnimatePresence>
              {dirtyIds.length > 0 && (
                <motion.span initial={{ scale: 0, width: 0 }} animate={{ scale: 1, width: "auto" }} exit={{ scale: 0, width: 0 }} className="grid min-w-5 place-items-center rounded-full bg-accent-ink px-1.5 text-[11px] text-accent">
                  {dirtyIds.length}
                </motion.span>
              )}
            </AnimatePresence>
          </Button>
        </div>

        {job.status.state === "error" && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-rec/30 bg-rec/8 p-4">
            <p className="flex items-center gap-2 font-semibold text-rec">
              <TriangleAlert className="size-4" /> Job lỗi{job.status.step ? ` ở bước “${STEP_INFO[job.status.step]?.label}”` : ""}
            </p>
            <p className="mt-1 font-mono text-sm break-words">{job.status.error}</p>
            {job.status.trace && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs font-semibold text-muted">Traceback</summary>
                <pre className="mt-2 max-h-64 overflow-auto rounded-xl bg-surface p-3 font-mono text-[11px] leading-relaxed">{job.status.trace}</pre>
              </details>
            )}
          </motion.div>
        )}

        <AnimatePresence initial={false}>
          {(busy || job.status.state === "error" || !p.outputs.video) && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
              <PipelineStepper job={job} />
            </motion.div>
          )}
        </AnimatePresence>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat icon={<Gauge className="size-4" />} label="Câu lệch thời lượng ≤ 10%" value={within} suffix="%" tone={within != null && within < 90 ? "text-warn" : "text-ok"} />
          <Stat icon={<TriangleAlert className="size-4" />} label="Câu có cảnh báo" value={warnCount} tone={warnCount ? "text-warn" : undefined} />
          <Stat icon={<Sparkles className="size-4" />} label={`RTF · xử lý ${secs(job.rtf.processing_time)}`} value={job.rtf.rtf} decimals={2} />
          <Stat icon={<Users className="size-4" />} label={`Nhân vật · ${editedCount} câu sửa tay`} value={spkIds.length} />
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(380px,1fr)]">
          {/* Cột trái: video + timeline */}
          <div className="min-w-0 space-y-4">
            <ComparePlayer
              srcUrl={sourceUrl(id)}
              dubUrl={dubUrl}
              project={p}
              active={active}
              viText={viText}
              speakerName={speakerName}
              speakerColor={color}
              disclaimer={disclaimer}
              onPrev={() => go(-1)}
              onNext={() => go(1)}
            />
            <WaveTimeline
              srcTrack={fileUrl(id, p.tracks.vocals ?? p.tracks.original, p.steps.separate?.finished_at ?? undefined)}
              dubTrack={fileUrl(id, p.tracks.dub, mixVersion)}
              segments={p.segments}
              activeId={active?.id}
              selectedId={selected}
              speakerIndex={speakerIndex}
              onSelect={onSelect}
              duration={p.duration ?? 0}
            />
          </div>

          {/* Cột phải: câu thoại / nhân vật */}
          <div className="min-w-0 xl:sticky xl:top-20 xl:self-start">
            <div className="flex flex-col rounded-2xl border border-line bg-surface/60 xl:h-[calc(100dvh-6.5rem)]">
              <div className="flex items-center gap-1 border-b border-line p-2">
                {(
                  [
                    ["segments", `Câu thoại`, p.segments.length],
                    ["speakers", `Nhân vật`, spkIds.length],
                  ] as const
                ).map(([k, label, n]) => (
                  <button key={k} onClick={() => setTab(k)} className={cx("relative rounded-xl px-3.5 py-2 text-sm font-semibold transition", tab === k ? "text-ink" : "text-muted hover:text-ink")}>
                    {tab === k && <motion.span layoutId="tab-pill" className="absolute inset-0 rounded-xl bg-surface shadow ring-1 ring-line" transition={{ type: "spring", stiffness: 500, damping: 38 }} />}
                    <span className="relative">
                      {label} <span className="ml-1 font-mono text-[11px] text-muted">{n}</span>
                    </span>
                  </button>
                ))}
                {tab === "segments" && (
                  <label className="ml-auto flex cursor-pointer items-center gap-2 px-2 text-xs font-medium text-muted">
                    <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} className="size-3.5 accent-[var(--color-accent)]" />
                    Theo đầu phát
                  </label>
                )}
              </div>

              {tab === "segments" ? (
                <>
                  <div className="space-y-2 border-b border-line p-3">
                    <div className="relative">
                      <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
                      <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Tìm trong câu gốc hoặc bản dịch…"
                        className="h-9 w-full rounded-xl border border-line bg-surface pr-3 pl-9 text-sm outline-none focus:border-line-strong"
                      />
                    </div>
                    <div className="flex gap-1.5 overflow-x-auto pb-0.5">
                      {(
                        [
                          ["all", "Tất cả", p.segments.length],
                          ["warn", "Cảnh báo", warnCount],
                          ["edited", "Đã sửa", editedCount + dirtyIds.filter((x) => !p.segments.find((s) => s.id === x)?.vi_locked).length],
                        ] as [Filter, string, number][]
                      ).map(([k, label, n]) => (
                        <button key={k} onClick={() => setFilter(k)} className={cx("shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold transition", filter === k ? "border-ink bg-ink text-bg" : "border-line text-muted hover:text-ink")}>
                          {label} <span className="opacity-60">{n}</span>
                        </button>
                      ))}
                      {spkIds.map((s) => (
                        <button
                          key={s}
                          onClick={() => setFilter(filter === `spk:${s}` ? "all" : `spk:${s}`)}
                          className={cx("inline-flex shrink-0 items-center gap-1.5 rounded-full border py-0.5 pr-2.5 pl-0.5 text-xs font-semibold transition", filter === `spk:${s}` ? "border-ink bg-ink text-bg" : "border-line text-muted hover:text-ink")}
                        >
                          <SpeakerAvatar name={speakerName(s)} color={color(s)} size={18} /> {speakerName(s)}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div ref={listRef} className="flex-1 space-y-2.5 overflow-y-auto p-3 max-xl:max-h-[70vh]">
                    {visible.length === 0 && (
                      <p className="py-12 text-center text-sm text-muted">{p.segments.length ? "Không có câu nào khớp bộ lọc." : busy ? "Câu thoại sẽ hiện ra sau bước Nhận dạng lời…" : "Chưa có câu thoại."}</p>
                    )}
                    {visible.map((s) => (
                      <SegmentCard
                        key={s.id}
                        seg={s}
                        draft={drafts[s.id]}
                        speakers={p.speakers}
                        color={color}
                        active={active?.id === s.id}
                        selected={selected === s.id}
                        busy={busy}
                        hasDub={!!dubUrl}
                        onSelect={onSelect}
                        onDraft={onDraft}
                        onPlay={onPlay}
                        onRegenerate={onRegenerate}
                        onUseTimbre={onUseTimbre}
                        onUnlock={onUnlock}
                      />
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex-1 overflow-y-auto p-3">
                  <SpeakerPanel
                    speakers={p.speakers}
                    segments={p.segments}
                    color={color}
                    timbreUrl={(rel) => fileUrl(id, rel, p.steps.synthesize?.finished_at ?? undefined)}
                    busy={busy}
                    onSave={async (spk, body) => {
                      try {
                        setJob(await api.patchSpeaker(id, spk, body));
                        toast.success("Đã lưu nhân vật", { description: "Bấm “Áp dụng thay đổi” để dịch lại theo ghi chú mới." });
                      } catch (e) {
                        fail("Không lưu được")(e);
                      }
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        {disclaimer && <p className="pt-4 text-center text-xs text-muted">{disclaimer}</p>}
      </main>
    </PlayerContext.Provider>
  );
}

export function JobPage({ id, disclaimer }: { id: string; disclaimer?: string }) {
  const { job, setJob, error, refresh, watch } = useJob(id);
  if (error && !job)
    return (
      <>
        <Header />
        <div className="mx-auto grid max-w-md place-items-center px-4 py-24 text-center">
          <p className="text-lg font-bold">Không mở được dự án</p>
          <p className="mt-1 text-sm text-muted">{error}</p>
          <Button className="mt-5" icon={<ArrowLeft className="size-4" />} onClick={() => navigate("#/")}>
            Về danh sách
          </Button>
        </div>
      </>
    );
  if (!job)
    return (
      <>
        <Header />
        <div className="mx-auto max-w-[1440px] space-y-4 px-4 py-5 sm:px-6">
          <div className="shimmer h-28 rounded-2xl" />
          <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <div className="shimmer aspect-video rounded-2xl" />
            <div className="shimmer h-[60vh] rounded-2xl" />
          </div>
        </div>
      </>
    );
  return <Studio key={id} job={job} setJob={setJob} refresh={refresh} watch={watch} disclaimer={disclaimer} />;
}
