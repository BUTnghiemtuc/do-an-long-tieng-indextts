import { ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin, { type Region } from "wavesurfer.js/dist/plugins/regions.js";
import TimelinePlugin from "wavesurfer.js/dist/plugins/timeline.js";
import { usePlayer } from "../hooks/usePlayer";
import type { Segment } from "../lib/api";
import { cssVar, useTheme } from "../lib/theme";
import { cx, IconButton } from "./ui";

/** Giải mã wav và rút gọn thành `n` đỉnh (|max| mỗi khoảng). */
async function peaksOf(url: string, n: number): Promise<{ peaks: Float32Array; duration: number } | null> {
  try {
    const buf = await (await fetch(url)).arrayBuffer();
    const audio = await new OfflineAudioContext(1, 1, 16000).decodeAudioData(buf);
    const data = audio.getChannelData(0);
    const out = new Float32Array(n);
    const block = data.length / n;
    for (let i = 0; i < n; i++) {
      let m = 0;
      const a = Math.floor(i * block);
      const b = Math.min(data.length, Math.floor((i + 1) * block));
      for (let j = a; j < b; j++) {
        const v = Math.abs(data[j]);
        if (v > m) m = v;
      }
      out[i] = m;
    }
    return { peaks: out, duration: audio.duration };
  } catch {
    return null;
  }
}

function hexA(color: string, alpha: number) {
  const c = color.startsWith("#") ? color : "#888888";
  return c + Math.round(alpha * 255).toString(16).padStart(2, "0");
}

interface Props {
  srcTrack?: string;
  dubTrack?: string;
  segments: Segment[];
  activeId: number | undefined;
  selectedId: number | undefined;
  speakerIndex: (spk: string) => number;
  onSelect: (s: Segment) => void;
  duration: number;
}

export function WaveTimeline({ srcTrack, dubTrack, segments, activeId, selectedId, speakerIndex, onSelect, duration }: Props) {
  const { master } = usePlayer();
  const { theme } = useTheme();
  const box = useRef<HTMLDivElement>(null);
  const ws = useRef<WaveSurfer | null>(null);
  const regions = useRef<InstanceType<typeof RegionsPlugin> | null>(null);
  const [zoom, setZoom] = useState(0);
  const [loading, setLoading] = useState(true);
  const [lanes, setLanes] = useState<{ peaks: Float32Array[]; duration: number } | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const segsRef = useRef(segments);
  segsRef.current = segments;

  // 1. Nạp sóng âm hai làn.
  useEffect(() => {
    let dead = false;
    setLoading(true);
    const n = Math.min(12000, Math.max(2000, Math.round(duration * 100)));
    Promise.all([srcTrack ? peaksOf(srcTrack, n) : null, dubTrack ? peaksOf(dubTrack, n) : null]).then(([a, b]) => {
      if (dead) return;
      const ok = [a, b].filter(Boolean) as { peaks: Float32Array; duration: number }[];
      setLanes(ok.length ? { peaks: ok.map((x) => x.peaks), duration: Math.max(...ok.map((x) => x.duration)) } : null);
      setLoading(false);
    });
    return () => {
      dead = true;
    };
  }, [srcTrack, dubTrack, duration]);

  // 2. Tạo wavesurfer gắn vào video master (bấm sóng âm = tua video).
  useEffect(() => {
    if (!box.current || !master || !lanes) return;
    const muted = cssVar("--color-muted");
    const accent = cssVar("--color-accent");
    const ink = cssVar("--color-ink");
    const rec = cssVar("--color-rec");
    const lane = (wave: string, prog: string) => ({ waveColor: wave, progressColor: prog, height: 52 });
    const r = RegionsPlugin.create();
    const t = TimelinePlugin.create({
      height: 18,
      timeInterval: 1,
      primaryLabelInterval: 5,
      style: { fontSize: "10px", color: muted, fontFamily: "JetBrains Mono Variable, monospace" },
    });
    const w = WaveSurfer.create({
      container: box.current,
      media: master,
      peaks: lanes.peaks,
      duration: lanes.duration || duration,
      splitChannels: lanes.peaks.length === 2 ? [lane(hexA(muted, 0.55), ink), lane(hexA(accent, 0.6), accent)] : [lane(hexA(muted, 0.55), ink)],
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      cursorColor: rec,
      cursorWidth: 2,
      normalize: true,
      dragToSeek: true,
      autoScroll: true,
      autoCenter: true,
      hideScrollbar: false,
      plugins: [r, t],
    });
    ws.current = w;
    regions.current = r;
    r.on("region-clicked", (reg: Region, e: MouseEvent) => {
      e.stopPropagation();
      const seg = segsRef.current.find((s) => String(s.id) === reg.id);
      if (seg) onSelectRef.current(seg);
    });
    return () => {
      w.destroy();
      ws.current = null;
      regions.current = null;
    };
    // segments xử lý ở effect dưới; chỉ dựng lại khi media/sóng/theme đổi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [master, lanes, theme]);

  // 3. Vùng câu thoại, tô theo màu nhân vật.
  useEffect(() => {
    const r = regions.current;
    if (!r) return;
    r.clearRegions();
    for (const s of segments) {
      const c = cssVar(`--color-spk-${speakerIndex(s.speaker) % 6}`);
      const hot = s.id === selectedId || s.id === activeId;
      const label = document.createElement("span");
      Object.assign(label.style, {
        font: "600 10px/1 'JetBrains Mono Variable', monospace",
        padding: "3px 5px",
        color: c,
        whiteSpace: "nowrap",
        pointerEvents: "none",
      });
      label.textContent = `#${s.id}${s.warnings.length ? " ⚠" : ""}`;
      const reg = r.addRegion({ id: String(s.id), start: s.start, end: s.end, color: hexA(c, hot ? 0.34 : 0.14), drag: false, resize: false, content: label });
      reg.element?.style.setProperty("border-left", `2px solid ${c}`);
      if (s.id === selectedId) reg.element?.style.setProperty("box-shadow", `inset 0 0 0 1.5px ${c}`);
    }
  }, [segments, activeId, selectedId, speakerIndex, lanes, master, theme]);

  useEffect(() => {
    try {
      ws.current?.zoom(zoom);
    } catch {
      /* chưa nạp xong */
    }
  }, [zoom]);

  return (
    <div className="rounded-2xl border border-line bg-surface">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2">
        <span className="text-sm font-bold">Timeline</span>
        <span className="hidden items-center gap-3 text-[11px] font-semibold text-muted sm:flex">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-4 rounded-sm bg-muted/60" /> Gốc
          </span>
          {lanes?.peaks.length === 2 && (
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-4 rounded-sm bg-accent/70" /> Tiếng Việt
            </span>
          )}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <IconButton label="Thu nhỏ" onClick={() => setZoom((z) => Math.max(0, z - 40))} disabled={zoom === 0}>
            <ZoomOut className="size-4" />
          </IconButton>
          <input
            type="range"
            min={0}
            max={400}
            step={10}
            value={zoom}
            onChange={(e) => setZoom(+e.target.value)}
            className="hidden w-24 accent-[var(--color-accent)] sm:block"
            aria-label="Phóng to timeline"
          />
          <IconButton label="Phóng to" onClick={() => setZoom((z) => Math.min(400, z + 40))}>
            <ZoomIn className="size-4" />
          </IconButton>
        </div>
      </div>
      <div className="relative px-2 pt-2 pb-1">
        {loading && (
          <div className="absolute inset-2 grid gap-2">
            <div className="shimmer rounded-lg" />
            <div className="shimmer rounded-lg" />
          </div>
        )}
        {!loading && !lanes && <p className="py-8 text-center text-sm text-muted">Chưa có audio để vẽ sóng âm.</p>}
        <div ref={box} className={cx("min-h-[124px]", loading && "opacity-0")} />
      </div>
    </div>
  );
}
