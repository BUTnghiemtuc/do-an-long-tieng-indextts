import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { EqBars, SpeakerAvatar } from "./ui";

// Minh hoạ trên trang chủ: một "màn hình phòng thu" với hai làn sóng âm (gốc / lồng tiếng),
// đầu phát chạy ngang và phụ đề đổi từ tiếng Anh sang tiếng Việt.
const LINES = [
  { spk: "Celia", c: "var(--color-spk-2)", en: "You never listened to me.", vi: "Anh chưa bao giờ nghe em cả." },
  { spk: "Tom", c: "var(--color-spk-3)", en: "I always listened. You just never said anything.", vi: "Anh luôn nghe mà. Chỉ là em chẳng bao giờ nói." },
  { spk: "Celia", c: "var(--color-spk-2)", en: "We have to leave before the sun comes up.", vi: "Mình phải đi trước khi trời sáng." },
];

function bars(seed: number, n: number) {
  let x = seed;
  return Array.from({ length: n }, (_, i) => {
    x = (x * 9301 + 49297) % 233280;
    const speech = Math.sin(i / 7) > -0.3 ? 1 : 0.15;
    return 0.15 + (x / 233280) * 0.85 * speech;
  });
}

export function HeroVisual() {
  const [i, setI] = useState(0);
  const [vi, setVi] = useState(false);
  useEffect(() => {
    const t = setInterval(() => {
      setVi((v) => {
        if (v) setI((k) => (k + 1) % LINES.length);
        return !v;
      });
    }, 2200);
    return () => clearInterval(t);
  }, []);
  const line = LINES[i];
  const a = useMemo(() => bars(7, 64), []);
  const b = useMemo(() => bars(23, 64), []);

  return (
    <div className="relative">
      <div className="absolute -inset-6 -z-10 rounded-[40px] bg-gradient-to-br from-accent/25 via-rec/10 to-spk-1/20 blur-3xl" />
      <motion.div
        initial={{ opacity: 0, y: 30, rotateX: 12 }}
        animate={{ opacity: 1, y: 0, rotateX: 0 }}
        transition={{ duration: 0.9, ease: [0.2, 0.8, 0.2, 1] }}
        style={{ transformPerspective: 1200 }}
        className="overflow-hidden rounded-3xl border border-line bg-surface shadow-2xl shadow-black/10"
      >
        {/* Màn hình */}
        <div className="relative aspect-[16/8] overflow-hidden bg-[#07070a]">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_40%,#3b2a1a_0%,transparent_55%),radial-gradient(ellipse_at_75%_60%,#1d2a3f_0%,transparent_55%)]" />
          <div className="absolute inset-x-0 top-0 h-[10%] bg-black" />
          <div className="absolute inset-x-0 bottom-0 h-[10%] bg-black" />
          <div className="absolute top-[14%] left-4 flex items-center gap-2 rounded-full bg-black/50 px-2.5 py-1 text-[11px] font-semibold text-white/90 backdrop-blur">
            <span className="size-1.5 animate-rec rounded-full bg-[#ff4d61]" /> REC · LỒNG TIẾNG
          </div>
          <div className="absolute top-[14%] right-4 rounded-full bg-black/50 px-2.5 py-1 font-mono text-[11px] text-white/70 backdrop-blur">
            {vi ? "VI" : "EN"} · 00:0{i * 3 + (vi ? 1 : 0)}:12
          </div>
          <div className="absolute inset-x-6 bottom-[16%] flex justify-center">
            <AnimatePresence mode="wait">
              <motion.p
                key={`${i}-${vi}`}
                initial={{ opacity: 0, y: 8, filter: "blur(6px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, y: -8, filter: "blur(6px)" }}
                transition={{ duration: 0.35 }}
                className="rounded-md bg-black/55 px-3 py-1.5 text-center text-sm font-semibold text-white sm:text-base"
              >
                <span className="mr-2 text-xs font-bold" style={{ color: line.c }}>
                  {line.spk}
                </span>
                {vi ? line.vi : line.en}
              </motion.p>
            </AnimatePresence>
          </div>
        </div>

        {/* Hai làn sóng âm */}
        <div className="space-y-2 p-4">
          {[
            { label: "Gốc", data: a, color: "var(--color-muted)", on: !vi },
            { label: "Tiếng Việt", data: b, color: "var(--color-accent)", on: vi },
          ].map((lane) => (
            <div key={lane.label} className="flex items-center gap-3">
              <span className={`w-16 text-[11px] font-semibold ${lane.on ? "text-ink" : "text-muted"}`}>{lane.label}</span>
              <div className="relative flex h-9 flex-1 items-center gap-[2px] overflow-hidden">
                {lane.data.map((h, k) => (
                  <motion.span
                    key={k}
                    className="flex-1 rounded-full"
                    style={{ background: lane.color, opacity: lane.on ? 0.95 : 0.35 }}
                    animate={{ height: `${h * (lane.on ? 100 : 60)}%` }}
                    transition={{ duration: 0.4, delay: k * 0.004 }}
                  />
                ))}
                <motion.span
                  className="absolute inset-y-0 w-px bg-rec shadow-[0_0_8px_var(--color-rec)]"
                  animate={{ left: ["0%", "100%"] }}
                  transition={{ duration: 4.4, ease: "linear", repeat: Infinity }}
                />
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between pt-2">
            <div className="flex -space-x-1.5">
              <SpeakerAvatar name="Celia" color="var(--color-spk-2)" size={26} />
              <SpeakerAvatar name="Tom" color="var(--color-spk-3)" size={26} />
            </div>
            <div className="flex items-center gap-2 text-[11px] font-semibold text-muted">
              <EqBars className="text-accent" /> Giữ giọng gốc · khớp thời lượng ±10%
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
