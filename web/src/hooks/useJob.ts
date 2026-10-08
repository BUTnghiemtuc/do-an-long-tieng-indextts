import { useCallback, useEffect, useRef, useState } from "react";
import { api, isBusy, type Job, type Status } from "../lib/api";

/**
 * Nạp job và theo dõi tiến độ qua SSE (/events). Mỗi khi một bước chạy xong hoặc job
 * kết thúc thì nạp lại dự án để thấy câu thoại, file audio mới.
 */
export function useJob(id: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(() => Date.now()); // đổi để làm mới URL media
  const esRef = useRef<EventSource | null>(null);

  const refresh = useCallback(async () => {
    try {
      const j = await api.job(id);
      setJob(j);
      setVersion(Date.now());
      setError(null);
      return j;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }, [id]);

  const watch = useCallback(() => {
    esRef.current?.close();
    const es = new EventSource(`/api/jobs/${id}/events`);
    esRef.current = es;
    let lastStep: string | null | undefined;
    es.onmessage = (m) => {
      const st: Status = JSON.parse(m.data);
      setJob((j) => (j ? { ...j, status: st } : j));
      const stepDone = st.frac === 1 && st.step !== lastStep;
      if (stepDone) lastStep = st.step;
      if (!isBusy(st)) {
        es.close();
        refresh();
      } else if (stepDone) {
        refresh();
      }
    };
    es.onerror = () => {
      es.close();
      // Mất kết nối: thử lại sau 2 s nếu job vẫn đang chạy.
      setTimeout(() => refresh().then((j) => j && isBusy(j.status) && watch()), 2000);
    };
  }, [id, refresh]);

  useEffect(() => {
    setJob(null);
    refresh().then((j) => j && isBusy(j.status) && watch());
    return () => esRef.current?.close();
  }, [refresh, watch]);

  return { job, setJob, error, refresh, watch, version };
}
