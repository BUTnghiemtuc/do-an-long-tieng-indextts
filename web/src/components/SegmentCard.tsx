import { AnimatePresence, motion } from "motion/react";
import { Lock, LockOpen, Mic, Play, RefreshCw, TriangleAlert } from "lucide-react";
import { memo, useLayoutEffect, useRef } from "react";
import type { Segment, Speaker } from "../lib/api";
import { syllables, tc } from "../lib/format";
import { cx, SpeakerAvatar } from "./ui";

export interface Draft {
  vi_text?: string;
  speaker?: string;
}

const STATUS: Record<Segment["status"], { label: string; cls: string }> = {
  new: { label: "Chưa dịch", cls: "bg-muted" },
  translated: { label: "Đã dịch", cls: "bg-spk-3" },
  synthesized: { label: "Đã sinh giọng", cls: "bg-accent" },
  done: { label: "Hoàn tất", cls: "bg-ok" },
  error: { label: "Lỗi", cls: "bg-rec" },
};

function methodLabel(m: string) {
  const [k, v] = m.split("=");
  return k === "duration_factor" ? `tốc độ ×${v}` : k === "stretch" ? `co giãn ×${v}` : k === "borrow" ? `mượn lặng ${v}` : m;
}

/** Thanh ngân sách âm tiết: vạch đỏ ở 100%, cho phép tới 115%. */
function SyllableMeter({ n, max }: { n: number; max: number | null }) {
  if (!max) return <span className="text-[11px] text-muted">{n} âm tiết</span>;
  const k = n / max;
  const tone = k > 1.15 ? "bg-rec" : k > 1 ? "bg-warn" : "bg-ok";
  return (
    <span className="flex items-center gap-2" title="Số âm tiết bản dịch / ngân sách theo thời lượng câu gốc">
      <span className="relative h-1.5 w-20 overflow-hidden rounded-full bg-surface-2">
        <motion.span className={cx("absolute inset-y-0 left-0 rounded-full", tone)} animate={{ width: `${Math.min(1, k / 1.3) * 100}%` }} transition={{ type: "spring", stiffness: 300, damping: 30 }} />
        <span className="absolute inset-y-0 w-px bg-ink/50" style={{ left: `${(1 / 1.3) * 100}%` }} />
      </span>
      <span className={cx("font-mono text-[11px] tabular", k > 1.15 ? "text-rec" : k > 1 ? "text-warn" : "text-muted")}>
        {n}/{max} âm tiết
      </span>
    </span>
  );
}

/** Tỉ lệ thời lượng bản lồng tiếng / bản gốc, vùng xanh là ±10%. */
function RatioGauge({ ratio }: { ratio: number | null }) {
  if (ratio == null) return null;
  const lo = 0.7, hi = 1.3;
  const pos = (Math.min(hi, Math.max(lo, ratio)) - lo) / (hi - lo);
  const bad = Math.abs(ratio - 1) > 0.1;
  return (
    <span className="flex items-center gap-2" title="Thời lượng bản lồng tiếng so với câu gốc (mục tiêu ±10%)">
      <span className="relative h-1.5 w-20 rounded-full bg-surface-2">
        <span className="absolute inset-y-0 rounded-full bg-ok/30" style={{ left: `${((0.9 - lo) / (hi - lo)) * 100}%`, right: `${((hi - 1.1) / (hi - lo)) * 100}%` }} />
        <motion.span
          className={cx("absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface", bad ? "bg-warn" : "bg-ok")}
          animate={{ left: `${pos * 100}%` }}
          transition={{ type: "spring", stiffness: 300, damping: 25 }}
        />
      </span>
      <span className={cx("font-mono text-[11px] tabular", bad ? "font-semibold text-warn" : "text-muted")}>{Math.round(ratio * 100)}%</span>
    </span>
  );
}

interface Props {
  seg: Segment;
  draft: Draft | undefined;
  speakers: Record<string, Speaker>;
  color: (spk: string) => string;
  active: boolean;
  selected: boolean;
  busy: boolean;
  hasDub: boolean;
  onSelect: (s: Segment) => void;
  onDraft: (id: number, d: Draft) => void;
  onPlay: (s: Segment, mode: "src" | "dub") => void;
  onRegenerate: (s: Segment) => void;
  onUseTimbre: (s: Segment) => void;
  onUnlock: (s: Segment) => void;
}

export const SegmentCard = memo(function SegmentCard({ seg, draft, speakers, color, active, selected, busy, hasDub, onSelect, onDraft, onPlay, onRegenerate, onUseTimbre, onUnlock }: Props) {
  const vi = draft?.vi_text ?? seg.vi_text;
  const spk = draft?.speaker ?? seg.speaker;
  const dirty = (draft?.vi_text != null && draft.vi_text !== seg.vi_text) || (draft?.speaker != null && draft.speaker !== seg.speaker);
  const ta = useRef<HTMLTextAreaElement>(null);
  const c = color(spk);

  // Ô nhập tự giãn theo nội dung.
  useLayoutEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${el.scrollHeight}px`;
  }, [vi]);

  return (
    <motion.article
      layout="position"
      data-seg={seg.id}
      onClick={(e) => {
        if (!(e.target as HTMLElement).closest("textarea,select,button")) onSelect(seg);
      }}
      className={cx(
        "group relative cursor-pointer rounded-2xl border bg-surface p-3.5 transition-[border-color,box-shadow] duration-200",
        selected ? "border-line-strong shadow-lg shadow-black/5" : "border-line hover:border-line-strong",
      )}
      style={{ borderLeft: `3px solid ${c}` }}
    >
      {active && (
        <motion.span
          layoutId="seg-active"
          className="pointer-events-none absolute -inset-px rounded-2xl"
          style={{ boxShadow: `0 0 0 2px ${c}, 0 0 28px -6px ${c}` }}
          transition={{ type: "spring", stiffness: 400, damping: 35 }}
        />
      )}

      <header className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <span className="font-mono text-xs font-bold text-muted">#{seg.id}</span>
        <span className="font-mono text-[11px] tabular text-muted">
          {tc(seg.start)} → {tc(seg.end)} · {(seg.end - seg.start).toFixed(1)}s
        </span>
        <label className="relative ml-auto flex items-center gap-1.5 rounded-full bg-surface-2 py-0.5 pr-2 pl-0.5 text-xs font-semibold">
          <SpeakerAvatar name={speakers[spk]?.name ?? spk} color={c} size={20} />
          <select
            value={spk}
            disabled={busy}
            onChange={(e) => onDraft(seg.id, { ...draft, speaker: e.target.value })}
            className="cursor-pointer appearance-none bg-transparent pr-1 outline-none"
            aria-label="Người nói"
          >
            {Object.entries(speakers).map(([k, v]) => (
              <option key={k} value={k}>
                {v.name}
              </option>
            ))}
          </select>
        </label>
        <span className="flex items-center gap-1.5 text-[11px] text-muted" title={STATUS[seg.status].label}>
          <span className={cx("size-2 rounded-full", STATUS[seg.status].cls)} />
          <span className="hidden sm:inline">{STATUS[seg.status].label}</span>
        </span>
      </header>

      <div className="mt-2.5 flex gap-2">
        <p className="flex-1 text-[13px] leading-relaxed text-muted">{seg.src_text}</p>
        <button
          onClick={() => onPlay(seg, "src")}
          className="inline-flex h-7 shrink-0 items-center gap-1 rounded-lg px-2 text-[11px] font-bold text-muted transition hover:bg-surface-2 hover:text-ink"
          title="Nghe câu gốc"
        >
          <Play className="size-3 fill-current" /> A
        </button>
      </div>

      <div className="mt-2 flex gap-2">
        <div className="relative flex-1">
          <textarea
            ref={ta}
            value={vi}
            rows={1}
            disabled={busy}
            placeholder="Chưa có bản dịch"
            onChange={(e) => onDraft(seg.id, { ...draft, vi_text: e.target.value })}
            onFocus={() => onSelect(seg)}
            className={cx(
              "block w-full resize-none overflow-hidden rounded-xl border bg-surface-2/50 px-3 py-2 text-[15px] leading-snug font-medium transition outline-none placeholder:text-muted/70 focus:bg-surface",
              dirty ? "border-accent ring-2 ring-accent/20" : "border-transparent focus:border-line-strong",
            )}
          />
          <AnimatePresence>
            {dirty && (
              <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} className="absolute -top-1 -right-1 size-2.5 rounded-full bg-accent ring-2 ring-surface" title="Chưa lưu" />
            )}
          </AnimatePresence>
        </div>
        <button
          onClick={() => onPlay(seg, "dub")}
          disabled={!hasDub && !seg.tts_audio}
          className="inline-flex h-7 shrink-0 items-center gap-1 self-start rounded-lg bg-accent/12 px-2 text-[11px] font-bold text-accent-strong transition hover:bg-accent/20 disabled:opacity-40"
          title="Nghe bản lồng tiếng"
        >
          <Play className="size-3 fill-current" /> B
        </button>
      </div>

      <footer className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-2">
        <SyllableMeter n={syllables(vi)} max={seg.max_syllables} />
        <RatioGauge ratio={seg.duration_ratio} />
        {seg.align_method.length > 0 && (
          <span className="flex flex-wrap gap-1">
            {seg.align_method.map((m) => (
              <span key={m} className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted">
                {methodLabel(m)}
              </span>
            ))}
          </span>
        )}
        {seg.vi_locked && (
          <button
            onClick={() => onUnlock(seg)}
            disabled={busy}
            className="group/lock inline-flex items-center gap-1 rounded-md bg-spk-1/12 px-1.5 py-0.5 text-[11px] font-semibold text-spk-1"
            title="Câu đã sửa tay, LLM sẽ không dịch đè. Bấm để mở khoá."
          >
            <Lock className="size-3 group-hover/lock:hidden" />
            <LockOpen className="hidden size-3 group-hover/lock:block" />
            Đã sửa tay
          </button>
        )}
      </footer>

      {seg.warnings.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {seg.warnings.map((w) => (
            <li key={w} className="inline-flex items-center gap-1 rounded-md bg-warn/10 px-2 py-0.5 text-[11px] font-semibold text-warn">
              <TriangleAlert className="size-3" /> {w}
            </li>
          ))}
        </ul>
      )}

      <div className={cx("mt-3 flex flex-wrap gap-2 overflow-hidden transition-all", selected || dirty ? "max-h-20 opacity-100" : "max-h-0 opacity-0 group-hover:max-h-20 group-hover:opacity-100")}>
        <button
          onClick={() => onRegenerate(seg)}
          disabled={busy}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-ink px-3 text-xs font-semibold text-bg transition hover:opacity-90 active:scale-95 disabled:opacity-40"
        >
          <RefreshCw className="size-3.5" /> {dirty ? "Lưu & tạo lại câu này" : "Tạo lại câu này"}
        </button>
        <button
          onClick={() => onUseTimbre(seg)}
          disabled={busy || !seg.style_prompt}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-3 text-xs font-semibold text-muted transition hover:bg-surface-2 hover:text-ink disabled:opacity-40"
          title="Dùng audio gốc của câu này làm giọng mẫu cho nhân vật"
        >
          <Mic className="size-3.5" /> Dùng làm giọng mẫu
        </button>
      </div>
    </motion.article>
  );
});
