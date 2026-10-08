import NumberFlow from "@number-flow/react";
import { motion } from "motion/react";
import { AudioLines, AudioWaveform, Captions, Check, Film, Languages, Mic, Timer, Users, X } from "lucide-react";
import { STEPS, type Job, type StepName } from "../lib/api";
import { secs, STEP_INFO } from "../lib/format";
import { cx } from "./ui";

const ICON: Record<StepName, typeof Film> = {
  extract: Film,
  separate: AudioWaveform,
  diarize: Users,
  transcribe: Captions,
  translate: Languages,
  synthesize: Mic,
  align: Timer,
  mix: AudioLines,
};

type StepState = "done" | "active" | "pending" | "error" | "skipped";

function stepStates(job: Job): Record<StepName, StepState> {
  const st = job.status;
  const out = {} as Record<StepName, StepState>;
  const run = st.steps && st.steps.length ? st.steps : [...STEPS];
  const busy = st.state === "running" || st.state === "queued";
  const cur = st.step ? run.indexOf(st.step) : -1;
  for (const s of STEPS) {
    const rec = !!job.project.steps[s];
    if (busy || st.state === "error") {
      const i = run.indexOf(s);
      if (i < 0) out[s] = rec ? "done" : "skipped";
      else if (i < cur) out[s] = "done";
      else if (i === cur) out[s] = st.state === "error" ? "error" : st.frac === 1 ? "done" : "active";
      else out[s] = "pending";
    } else out[s] = rec ? "done" : "pending";
  }
  return out;
}

export function PipelineStepper({ job }: { job: Job }) {
  const states = stepStates(job);
  const doneCount = STEPS.filter((s) => states[s] === "done").length;
  const activeIdx = STEPS.findIndex((s) => states[s] === "active" || states[s] === "error");
  const frac = job.status.frac ?? 0;
  const progress = activeIdx >= 0 ? (activeIdx + frac) / (STEPS.length - 1) : doneCount === STEPS.length ? 1 : (doneCount - 1) / (STEPS.length - 1);
  const overall = Math.round(((activeIdx >= 0 ? activeIdx + frac : doneCount) / STEPS.length) * 100);

  return (
    <div className="rounded-2xl border border-line bg-surface p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-sm font-bold">Tiến độ lồng tiếng</span>
        <span className="font-mono text-2xl font-bold tabular text-accent-strong">
          <NumberFlow value={Math.max(0, Math.min(100, overall))} suffix="%" />
        </span>
        {job.status.msg && job.status.state !== "done" && (
          <span className="truncate text-sm text-muted">
            {job.status.step ? `${STEP_INFO[job.status.step]?.label ?? job.status.step}: ` : ""}
            {job.status.msg}
          </span>
        )}
      </div>

      <div className="-mx-2 -my-3 overflow-x-auto px-2 py-3">
        <div className="relative grid min-w-[720px] grid-cols-8">
          {/* Đường nối */}
          <div className="absolute top-5 right-[6.25%] left-[6.25%] h-[3px] rounded-full bg-line" />
          <motion.div
            className="absolute top-5 left-[6.25%] h-[3px] rounded-full bg-gradient-to-r from-accent to-rec"
            initial={false}
            animate={{ width: `${Math.max(0, progress) * 87.5}%` }}
            transition={{ type: "spring", stiffness: 80, damping: 20 }}
          />
          {STEPS.map((s, i) => {
            const state = states[s];
            const Icon = ICON[s];
            const elapsed = job.project.steps[s]?.elapsed;
            return (
              <div key={s} className="relative flex flex-col items-center text-center">
                <div className="relative grid size-10 place-items-center">
                  {state === "active" && (
                    <>
                      <span className="absolute -inset-1.5 animate-spin-slow rounded-full bg-[conic-gradient(from_0deg,var(--color-accent),transparent_40%,var(--color-rec),transparent_80%,var(--color-accent))] opacity-90" />
                      <span className="absolute -inset-3 animate-ping rounded-full bg-accent/20 [animation-duration:2s]" />
                    </>
                  )}
                  <motion.span
                    initial={false}
                    animate={{ scale: state === "active" ? 1.08 : 1 }}
                    className={cx(
                      "relative z-10 grid size-10 place-items-center rounded-full border-2 transition-colors duration-300",
                      state === "done" && "border-accent bg-accent text-accent-ink",
                      state === "active" && "border-surface bg-surface text-accent-strong",
                      state === "pending" && "border-line bg-surface text-muted",
                      state === "skipped" && "border-dashed border-line bg-surface text-muted/60",
                      state === "error" && "border-rec bg-rec text-white",
                    )}
                  >
                    {state === "done" ? (
                      <motion.span initial={{ scale: 0, rotate: -45 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 500, damping: 20 }}>
                        <Check className="size-5" strokeWidth={3} />
                      </motion.span>
                    ) : state === "error" ? (
                      <X className="size-5" strokeWidth={3} />
                    ) : (
                      <Icon className="size-[18px]" />
                    )}
                  </motion.span>
                </div>
                <span className={cx("mt-2.5 text-[13px] leading-tight font-semibold", state === "pending" || state === "skipped" ? "text-muted" : "text-ink")}>
                  {STEP_INFO[s].label}
                </span>
                <span className="mt-0.5 text-[11px] text-muted">
                  {state === "active" ? (
                    <span className="font-mono font-semibold text-accent-strong">
                      <NumberFlow value={Math.round(frac * 100)} suffix="%" />
                    </span>
                  ) : elapsed != null && state === "done" ? (
                    <span className="font-mono">{secs(elapsed)}</span>
                  ) : (
                    STEP_INFO[s].tool
                  )}
                </span>
                <span className="sr-only">Bước {i + 1}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
