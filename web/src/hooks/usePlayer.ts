import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

export type AudioMode = "dub" | "src";

/**
 * Hai video chạy đồng bộ: `master` là bản lồng tiếng (nếu đã có), `slave` là bản gốc.
 * Chỉ một bản phát tiếng tại một thời điểm; đổi chế độ thì âm lượng chuyển chéo trong 250 ms
 * nên nghe A/B không bị khựng.
 */
export function usePlayerState(hasDub: boolean) {
  const masterRef = useRef<HTMLVideoElement | null>(null);
  const slaveRef = useRef<HTMLVideoElement | null>(null);
  const [master, setMaster] = useState<HTMLVideoElement | null>(null);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [mode, setModeState] = useState<AudioMode>(hasDub ? "dub" : "src");
  const stopAt = useRef<number | null>(null);
  const fade = useRef<number>(0);

  useEffect(() => {
    if (!hasDub) setModeState("src");
  }, [hasDub]);

  /** Video nào đang phát tiếng theo chế độ hiện tại. */
  const voices = useCallback(
    (m: AudioMode) => {
      const dub = hasDub ? masterRef.current : null;
      const src = hasDub ? slaveRef.current : masterRef.current;
      return m === "dub" ? { on: dub, off: src } : { on: src, off: dub };
    },
    [hasDub],
  );

  const applyVolumes = useCallback(
    (m: AudioMode, animate: boolean) => {
      const { on, off } = voices(m);
      cancelAnimationFrame(fade.current);
      const v0 = on && !on.muted ? on.volume : 0;
      if (on) on.muted = false;
      if (!animate) {
        if (on) on.volume = 1;
        if (off) off.muted = true;
        return;
      }
      const t0 = performance.now();
      const step = (now: number) => {
        const k = Math.min(1, (now - t0) / 250);
        if (on) on.volume = v0 + (1 - v0) * k;
        if (off) off.volume = 1 - k;
        if (k < 1) fade.current = requestAnimationFrame(step);
        else if (off) off.muted = true;
      };
      fade.current = requestAnimationFrame(step);
    },
    [voices],
  );

  const setMode = useCallback(
    (m: AudioMode) => {
      if (m === "dub" && !hasDub) return;
      setModeState(m);
      applyVolumes(m, true);
    },
    [applyVolumes, hasDub],
  );

  // Đồng bộ slave theo master + cập nhật thời gian bằng rAF (mượt hơn timeupdate).
  useEffect(() => {
    const m = master;
    if (!m) return;
    applyVolumes(mode, false);
    let raf = 0;
    const tick = () => {
      setTime(m.currentTime);
      const s = slaveRef.current;
      if (s && hasDub && Math.abs(s.currentTime - m.currentTime) > 0.12) s.currentTime = m.currentTime;
      if (stopAt.current != null && m.currentTime >= stopAt.current) {
        stopAt.current = null;
        m.pause();
      }
      if (!m.paused) raf = requestAnimationFrame(tick);
    };
    const onPlay = () => {
      setPlaying(true);
      if (hasDub) slaveRef.current?.play().catch(() => {});
      raf = requestAnimationFrame(tick);
    };
    const onPause = () => {
      setPlaying(false);
      slaveRef.current?.pause();
      cancelAnimationFrame(raf);
      setTime(m.currentTime);
    };
    const onSeek = () => {
      if (hasDub && slaveRef.current) slaveRef.current.currentTime = m.currentTime;
      setTime(m.currentTime);
    };
    const onMeta = () => setDuration(m.duration || 0);
    m.addEventListener("play", onPlay);
    m.addEventListener("pause", onPause);
    m.addEventListener("seeked", onSeek);
    m.addEventListener("timeupdate", onSeek);
    m.addEventListener("loadedmetadata", onMeta);
    onMeta();
    return () => {
      cancelAnimationFrame(raf);
      m.removeEventListener("play", onPlay);
      m.removeEventListener("pause", onPause);
      m.removeEventListener("seeked", onSeek);
      m.removeEventListener("timeupdate", onSeek);
      m.removeEventListener("loadedmetadata", onMeta);
    };
    // mode cố ý không nằm trong deps: đổi mode đã có applyVolumes riêng.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [master, hasDub]);

  const toggle = useCallback(() => {
    const m = masterRef.current;
    if (!m) return;
    stopAt.current = null;
    if (m.paused) m.play().catch(() => {});
    else m.pause();
  }, []);

  const seek = useCallback((t: number) => {
    const m = masterRef.current;
    if (m) m.currentTime = Math.max(0, t);
  }, []);

  /** Nghe một đoạn [start, end] theo chế độ chỉ định, tự dừng ở cuối đoạn. */
  const playRange = useCallback(
    (start: number, end: number, m?: AudioMode) => {
      const v = masterRef.current;
      if (!v) return;
      if (m) setMode(m);
      v.currentTime = Math.max(0, start - 0.05);
      stopAt.current = end + 0.1;
      v.play().catch(() => {});
    },
    [setMode],
  );

  const bindMaster = useCallback((el: HTMLVideoElement | null) => {
    masterRef.current = el;
    setMaster(el);
  }, []);
  const bindSlave = useCallback((el: HTMLVideoElement | null) => {
    slaveRef.current = el;
  }, []);

  return { bindMaster, bindSlave, master, time, duration, playing, mode, setMode, toggle, seek, playRange, hasDub };
}

export type Player = ReturnType<typeof usePlayerState>;
export const PlayerContext = createContext<Player | null>(null);
export const usePlayer = () => {
  const p = useContext(PlayerContext);
  if (!p) throw new Error("usePlayer cần PlayerContext");
  return p;
};
