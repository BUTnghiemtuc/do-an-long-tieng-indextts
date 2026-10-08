import type { JobState, StepName } from "./api";

/** 75.3 -> "1:15.3" */
export function tc(t: number | null | undefined, digits = 1): string {
  if (t == null || !isFinite(t)) return "–:––";
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${m}:${s.toFixed(digits).padStart(digits ? 3 + digits : 2, "0")}`;
}

export function secs(t: number): string {
  return t < 10 ? `${t.toFixed(1)}s` : t < 60 ? `${Math.round(t)}s` : `${Math.floor(t / 60)}m${String(Math.round(t % 60)).padStart(2, "0")}`;
}

/** Số âm tiết tiếng Việt = số tiếng cách nhau bởi khoảng trắng (bỏ dấu câu đứng riêng). */
export function syllables(text: string): number {
  return text.split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length;
}

/** Job id dạng 20261007-213015-ab12cd -> Date */
export function jobDate(id: string): Date | null {
  const m = /^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/.exec(id);
  return m ? new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) : null;
}

export function relTime(d: Date | null): string {
  if (!d) return "";
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "vừa xong";
  if (diff < 3600) return `${Math.floor(diff / 60)} phút trước`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} giờ trước`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} ngày trước`;
  return d.toLocaleDateString("vi-VN");
}

export const STATE_LABEL: Record<JobState, string> = {
  created: "Mới tạo",
  queued: "Đang chờ",
  running: "Đang lồng tiếng",
  done: "Hoàn tất",
  error: "Lỗi",
  unknown: "Không rõ",
};

export const STEP_INFO: Record<StepName, { label: string; desc: string; tool: string }> = {
  extract: { label: "Tách audio", desc: "Lấy âm thanh từ video", tool: "ffmpeg" },
  separate: { label: "Tách giọng", desc: "Giọng nói ↔ nhạc nền & hiệu ứng", tool: "Demucs" },
  diarize: { label: "Nhận diện người nói", desc: "Ai nói, khi nào", tool: "pyannote" },
  transcribe: { label: "Nhận dạng lời", desc: "Lời thoại gốc + cắt câu", tool: "WhisperX" },
  translate: { label: "Dịch theo cảnh", desc: "Giữ xưng hô, khớp số âm tiết", tool: "Claude" },
  synthesize: { label: "Sinh giọng", desc: "Giữ giọng & cảm xúc nhân vật", tool: "IndexTTS" },
  align: { label: "Căn thời lượng", desc: "Co giãn, mượn khoảng lặng", tool: "rubberband" },
  mix: { label: "Trộn & xuất", desc: "Loudness, nhạc nền, MP4 + SRT", tool: "ffmpeg" },
};

export const LANGS: Record<string, string> = { en: "Tiếng Anh", zh: "Tiếng Trung", ja: "Tiếng Nhật", ko: "Tiếng Hàn", vi: "Tiếng Việt" };
