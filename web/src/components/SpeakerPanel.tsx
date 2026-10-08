import { motion } from "motion/react";
import { Pause, Play, Save } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Segment, Speaker } from "../lib/api";
import { secs } from "../lib/format";
import { Button, EqBars, SpeakerAvatar } from "./ui";

interface Props {
  speakers: Record<string, Speaker>;
  segments: Segment[];
  color: (spk: string) => string;
  timbreUrl: (rel: string | null) => string | undefined;
  busy: boolean;
  onSave: (spk: string, body: { name: string; notes: string }) => Promise<void>;
}

function SpeakerCard({ id, sp, segs, color, url, busy, onSave, index }: { id: string; sp: Speaker; segs: Segment[]; color: string; url?: string; busy: boolean; onSave: Props["onSave"]; index: number }) {
  const [name, setName] = useState(sp.name);
  const [notes, setNotes] = useState(sp.notes);
  const [saving, setSaving] = useState(false);
  const [playing, setPlaying] = useState(false);
  const audio = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    setName(sp.name);
    setNotes(sp.notes);
  }, [sp.name, sp.notes]);
  const dirty = name !== sp.name || notes !== sp.notes;
  const talk = segs.reduce((t, s) => t + (s.end - s.start), 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="relative overflow-hidden rounded-2xl border border-line bg-surface p-4"
    >
      <div className="pointer-events-none absolute -top-16 -right-16 size-40 rounded-full opacity-20 blur-2xl" style={{ background: color }} />
      <div className="relative flex items-center gap-3">
        <SpeakerAvatar name={name || id} color={color} size={42} />
        <div className="min-w-0 flex-1">
          <input
            value={name}
            disabled={busy}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg bg-transparent px-1 py-0.5 text-base font-bold outline-none hover:bg-surface-2 focus:bg-surface-2"
            aria-label="Tên nhân vật"
          />
          <p className="px-1 text-xs text-muted">
            <span className="font-mono">{id}</span> · {segs.length} câu · {secs(talk)} lời thoại
          </p>
        </div>
      </div>

      <label className="relative mt-3 block">
        <span className="text-[11px] font-semibold tracking-wide text-muted uppercase">Ghi chú xưng hô</span>
        <textarea
          value={notes}
          disabled={busy}
          rows={2}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="vd: nữ, 25 tuổi, người yêu của Tom, gọi Tom là “anh”"
          className="mt-1 block w-full resize-none rounded-xl border border-line bg-surface-2/50 px-3 py-2 text-sm outline-none focus:border-line-strong focus:bg-surface"
        />
      </label>

      <div className="relative mt-3 flex items-center gap-2">
        {url ? (
          <>
            <audio ref={audio} src={url} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
            <button
              onClick={() => (audio.current?.paused ? audio.current.play() : audio.current?.pause())}
              className="inline-flex h-8 items-center gap-2 rounded-lg px-2.5 text-xs font-semibold transition"
              style={{ background: `color-mix(in oklab, ${color} 15%, transparent)`, color }}
            >
              {playing ? <Pause className="size-3.5 fill-current" /> : <Play className="size-3.5 fill-current" />}
              Giọng mẫu
              <EqBars n={4} playing={playing} className="h-3" />
            </button>
          </>
        ) : (
          <span className="text-xs text-muted">Chưa có giọng mẫu (sau bước Sinh giọng)</span>
        )}
        <Button
          size="sm"
          variant={dirty ? "primary" : "ghost"}
          disabled={!dirty || busy}
          loading={saving}
          icon={<Save className="size-3.5" />}
          className="ml-auto"
          onClick={async () => {
            setSaving(true);
            try {
              await onSave(id, { name, notes });
            } finally {
              setSaving(false);
            }
          }}
        >
          Lưu
        </Button>
      </div>
    </motion.div>
  );
}

export function SpeakerPanel({ speakers, segments, color, timbreUrl, busy, onSave }: Props) {
  const ids = Object.keys(speakers);
  if (!ids.length) return <p className="py-10 text-center text-sm text-muted">Chưa nhận diện người nói (chờ bước Nhận diện người nói).</p>;
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        Đổi ghi chú sẽ dịch lại các câu chưa sửa tay của nhân vật đó để chọn xưng hô cho đúng. Muốn đổi giọng mẫu, chọn “Dùng làm giọng mẫu” ở một câu thoại.
      </p>
      {ids.map((id, i) => (
        <SpeakerCard key={id} id={id} index={i} sp={speakers[id]} segs={segments.filter((s) => s.speaker === id)} color={color(id)} url={timbreUrl(speakers[id].timbre_prompt)} busy={busy} onSave={onSave} />
      ))}
    </div>
  );
}
