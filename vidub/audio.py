"""Tiện ích âm thanh: đọc/ghi, resample, cắt đoạn, co giãn thời gian qua ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg lỗi ({' '.join(cmd)}):\n{proc.stderr.strip()}")


def probe_duration(path: str | Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def load(path: str | Path, sr: int | None = None, mono: bool = True) -> tuple[np.ndarray, int]:
    """Trả về (float32 [n] nếu mono, [n, ch] nếu không), sample rate."""
    wav, file_sr = sf.read(str(path), dtype="float32", always_2d=True)
    if mono:
        wav = wav.mean(axis=1)
    if sr is not None and sr != file_sr:
        wav = resample(wav, file_sr, sr)
        file_sr = sr
    return wav, file_sr


def resample(wav: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return wav
    g = gcd(sr_in, sr_out)
    return resample_poly(wav, sr_out // g, sr_in // g, axis=0).astype(np.float32)


def save(path: str | Path, wav: np.ndarray, sr: int) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), wav, sr, subtype="PCM_16" if path.suffix == ".wav" else None)
    return path


def duration(path: str | Path) -> float:
    info = sf.info(str(path))
    return info.frames / info.samplerate


def cut(wav: np.ndarray, sr: int, start: float, end: float) -> np.ndarray:
    a = max(0, int(round(start * sr)))
    b = min(len(wav), int(round(end * sr)))
    return wav[a:b]


def fade(wav: np.ndarray, sr: int, fade_in: float = 0.01, fade_out: float = 0.02) -> np.ndarray:
    wav = wav.copy()
    n_in, n_out = min(len(wav), int(fade_in * sr)), min(len(wav), int(fade_out * sr))
    if n_in:
        wav[:n_in] *= np.linspace(0, 1, n_in, dtype=np.float32)
    if n_out:
        wav[-n_out:] *= np.linspace(1, 0, n_out, dtype=np.float32)
    return wav


def trim_silence(wav: np.ndarray, sr: int, thresh_db: float = -45.0, pad: float = 0.03) -> np.ndarray:
    """Cắt im lặng hai đầu (TTS hay sinh thừa khoảng lặng, làm sai thời lượng thật)."""
    if len(wav) == 0:
        return wav
    frame = max(1, int(0.01 * sr))
    n = len(wav) // frame
    if n == 0:
        return wav
    rms = np.sqrt(np.mean(wav[: n * frame].reshape(n, frame) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms / (np.max(rms) + 1e-12) + 1e-12)
    voiced = np.where(db > thresh_db)[0]
    if len(voiced) == 0:
        return wav
    a = max(0, voiced[0] * frame - int(pad * sr))
    b = min(len(wav), (voiced[-1] + 1) * frame + int(pad * sr))
    return wav[a:b]


def time_stretch(src: str | Path, dst: str | Path, rate: float) -> Path:
    """Đổi tốc độ, giữ cao độ. rate > 1 là nói nhanh hơn (ngắn lại).

    Dùng rubberband CLI nếu có (chất lượng tốt hơn), ngược lại dùng ffmpeg atempo.
    """
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if abs(rate - 1.0) < 1e-3:
        shutil.copyfile(src, dst)
        return dst
    if shutil.which("rubberband"):
        subprocess.run(
            ["rubberband", "-q", "-T", f"{rate:.5f}", "--formant", str(src), str(dst)],
            check=True, capture_output=True,
        )
    else:
        run_ffmpeg(["-i", str(src), "-filter:a", f"atempo={rate:.5f}", str(dst)])
    return dst


def rms_db(wav: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(wav ** 2) + 1e-12)))
