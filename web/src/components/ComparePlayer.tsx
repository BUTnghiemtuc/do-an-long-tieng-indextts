import { AnimatePresence, motion } from "motion/react";
import { Columns2, Maximize2, Pause, Play, RectangleHorizontal, SkipBack, SkipForward, Subtitles } from "lucide-react";
import { useRef, useState } from "react";
import { usePlayer } from "../hooks/usePlayer";
import type { Project, Segment } from "../lib/api";
import { tc } from "../lib/format";
import { cx, IconButton, Kbd } from "./ui";

interface Props {
  srcUrl: string;
  dubUrl?: string;
  project: Project;
  active: Segment | undefined;
  viText: (s: Segment) => string;
  speakerName: (spk: string) => string;
  speakerColor: (spk: string) => string;
  disclaimer?: string;
  onPrev: () => void;
  onNext: () => void;
}

/** Bộ phát so sánh: một khung chung (nghe A/B) hoặc hai khung cạnh nhau. */
export function ComparePlayer({ srcUrl, dubUrl, project, active, viText, speakerName, speakerColor, disclaimer, onPrev, onNext }: Props) {
  const p = usePlayer();
  const [split, setSplit] = useState(false);
  const [subs, setSubs] = useState(true);
  const stage = useRef<HTMLDivElement>(null);
  const hasDub = !!dubUrl;
  const dur = p.duration || project.duration || 0;

  const subtitle = active && (p.mode === "dub" ? viText(active) : active.src_text);

  const video = (url: string, role: "master" | "slave", label: string, on: boolean) => (
    <div key={role} className={cx("overflow-hidden bg-black", split ? "relative aspect-video rounded-xl" : "absolute inset-0")}>
      <video
        ref={role === "master" ? p.bindMaster : p.bindSlave}
        src={url}
        playsInline
        preload="auto"
        onClick={p.toggle}
        className="size-full object-contain"
      />
      {split && (
        <span className={cx("absolute top-2 left-2 rounded-md px-2 py-0.5 text-[11px] font-bold backdrop-blur", on ? "bg-accent text-accent-ink" : "bg-black/50 text-white/80")}>
          {label}
        </span>
      )}
    </div>
  );

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-surface">
      <div ref={stage} className="relative bg-black">
        <div className={cx(split ? "grid grid-cols-2 gap-2 p-2" : "relative aspect-video")}>
          {hasDub ? (
            <>
              {/* Bản gốc nằm dưới; ở chế độ một khung bản lồng tiếng che lên (cùng hình) */}
              {video(srcUrl, "slave", "Gốc", p.mode === "src")}
              {video(dubUrl!, "master", "Tiếng Việt", p.mode === "dub")}
            </>
          ) : (
            video(srcUrl, "master", "Gốc", true)
          )}
        </div>

        {/* Phụ đề trực tiếp: hiện cả bản nháp đang gõ */}
        <AnimatePresence mode="wait">
          {subs && subtitle && (
            <motion.div
              key={`${active!.id}-${p.mode}`}
              initial={{ opacity: 0, y: 6, filter: "blur(4px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, filter: "blur(4px)" }}
              transition={{ duration: 0.18 }}
              className="pointer-events-none absolute inset-x-2 bottom-2 flex justify-center sm:inset-x-4 sm:bottom-4"
            >
              <p className="max-w-[90%] rounded-lg bg-black/65 px-2.5 py-1 text-center text-[13px] leading-snug font-semibold text-white backdrop-blur-sm sm:max-w-[85%] sm:px-3 sm:py-1.5 sm:text-lg">
                <span className="mr-2 text-xs font-bold" style={{ color: speakerColor(active!.speaker) }}>
                  {speakerName(active!.speaker)}
                </span>
                {subtitle}
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {!split && (
          <div className="pointer-events-none absolute top-3 left-3 flex items-center gap-2">
            <span className="rounded-full bg-black/55 px-2.5 py-1 text-[11px] font-bold text-white backdrop-blur">
              {p.mode === "dub" ? "VI · Bản lồng tiếng" : `${project.src_lang.toUpperCase()} · Bản gốc`}
            </span>
          </div>
        )}
        {disclaimer && hasDub && (
          <span className="pointer-events-none absolute top-3 right-3 rounded-full bg-black/55 px-2.5 py-1 text-[10px] font-semibold text-white/75 backdrop-blur" title={disclaimer}>
            Giọng do AI tạo
          </span>
        )}

        {/* Nút phát lớn ở giữa khi dừng */}
        <AnimatePresence>
          {!p.playing && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.3 }}
              onClick={p.toggle}
              aria-label="Phát"
              className="absolute top-1/2 left-1/2 grid size-16 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white/15 text-white ring-1 ring-white/30 backdrop-blur-md transition hover:bg-white/25"
            >
              <Play className="ml-1 size-7 fill-current" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Thanh điều khiển */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5">
        <IconButton label="Câu trước (←)" onClick={onPrev}>
          <SkipBack className="size-4" />
        </IconButton>
        <button
          onClick={p.toggle}
          aria-label={p.playing ? "Tạm dừng" : "Phát"}
          className="grid size-10 place-items-center rounded-full bg-ink text-bg transition hover:scale-105 active:scale-95"
        >
          {p.playing ? <Pause className="size-4 fill-current" /> : <Play className="ml-0.5 size-4 fill-current" />}
        </button>
        <IconButton label="Câu sau (→)" onClick={onNext}>
          <SkipForward className="size-4" />
        </IconButton>
        <span className="ml-1 font-mono text-[13px] tabular text-muted">
          <span className="text-ink">{tc(p.time)}</span> / {tc(dur)}
        </span>

        <div className="ml-auto flex items-center gap-2">
          <span className="hidden items-center gap-1 text-[11px] text-muted lg:flex">
            <Kbd>Space</Kbd> phát <Kbd>A</Kbd> đổi tiếng
          </span>
          {/* Công tắc A/B */}
          <div className="relative flex rounded-xl bg-surface-2 p-1 text-[13px] font-semibold" role="radiogroup" aria-label="Nghe">
            {(["src", "dub"] as const).map((m) => (
              <button
                key={m}
                role="radio"
                aria-checked={p.mode === m}
                disabled={m === "dub" && !hasDub}
                onClick={() => p.setMode(m)}
                className={cx("relative rounded-lg px-3 py-1.5 transition disabled:opacity-40", p.mode === m ? (m === "dub" ? "text-accent-ink" : "text-ink") : "text-muted hover:text-ink")}
              >
                {p.mode === m && (
                  <motion.span
                    layoutId="ab-pill"
                    className={cx("absolute inset-0 rounded-lg shadow", m === "dub" ? "bg-accent" : "bg-surface ring-1 ring-line")}
                    transition={{ type: "spring", stiffness: 500, damping: 35 }}
                  />
                )}
                <span className="relative">{m === "src" ? "A · Gốc" : "B · Lồng tiếng"}</span>
              </button>
            ))}
          </div>
          <IconButton label={subs ? "Ẩn phụ đề" : "Hiện phụ đề"} onClick={() => setSubs((v) => !v)} className={subs ? "text-ink" : ""}>
            <Subtitles className="size-4" />
          </IconButton>
          <IconButton label={split ? "Một khung" : "Hai khung cạnh nhau"} onClick={() => setSplit((v) => !v)} disabled={!hasDub}>
            {split ? <RectangleHorizontal className="size-4" /> : <Columns2 className="size-4" />}
          </IconButton>
          <IconButton label="Toàn màn hình" onClick={() => stage.current?.requestFullscreen?.()}>
            <Maximize2 className="size-4" />
          </IconButton>
        </div>
      </div>
    </div>
  );
}
