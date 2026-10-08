"""Các chỉ số đánh giá. Mô hình chấm điểm nạp lười, một lần mỗi tiến trình.

| Chỉ số  | Mô hình                                   |
| CER/WER | ASR tiếng Việt: parakeet-ctc-0.6b-vi / Whisper large-v3 |
| SS      | ECAPA-TDNN speechbrain/spkrec-ecapa-voxceleb (cosine) — thang đo thường gặp trong paper |
| SS_wavlm| WavLM-base-plus-sv (cosine x-vector) — điểm dồn sát 0,9+, chỉ để so nội bộ |
| UTMOS   | SpeechMOS utmos22_strong (huấn luyện chủ yếu trên tiếng Anh — ghi hạn chế) |
| ES      | emotion2vec_plus_large (cosine embedding câu gốc ↔ câu lồng tiếng) |
| EMO     | nhãn cảm xúc emotion2vec (5 lớp: angry/happy/neutral/sad/surprised) của câu sinh ra |
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from data_prep.vi_normalize import normalize
from vidub.audio import load


def _norm_for_wer(s: str) -> str:
    s = normalize(s).lower()
    for ch in ",.!?;:…\"'-–—":
        s = s.replace(ch, " ")
    return " ".join(s.split())


def cer(ref: str, hyp: str) -> float:
    import jiwer

    r = _norm_for_wer(ref)
    return float(jiwer.cer(r, _norm_for_wer(hyp))) if r else float("nan")


def wer(ref: str, hyp: str) -> float:
    import jiwer

    r = _norm_for_wer(ref)
    return float(jiwer.wer(r, _norm_for_wer(hyp))) if r else float("nan")


def _device():
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


# ------------------------------------------------------------------ ASR
@lru_cache(maxsize=2)
def asr_model(name: str = "parakeet"):
    if name == "parakeet":
        from data_prep.filter import ParakeetASR

        return ParakeetASR()
    from data_prep.filter import WhisperASR

    return WhisperASR()


def transcribe(paths: list[str], name: str = "parakeet") -> list[str]:
    return asr_model(name)(paths)


# ------------------------------------------------------------------ speaker similarity
_CACHE = Path(__file__).resolve().parents[1] / ".cache"


@lru_cache(maxsize=1)
def _ecapa():
    from speechbrain.inference.speaker import EncoderClassifier

    return EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                          savedir=str(_CACHE / "speechbrain" / "spkrec-ecapa-voxceleb"),
                                          run_opts={"device": _device()})


@lru_cache(maxsize=4096)
def ecapa_embedding(path: str) -> np.ndarray:
    import torch

    wav, _ = load(path, sr=16000)
    with torch.inference_mode():
        emb = _ecapa().encode_batch(torch.from_numpy(wav)[None].to(_device())).reshape(-1)
    return torch.nn.functional.normalize(emb, dim=-1).cpu().numpy()


def speaker_similarity(a: str, b: str) -> float:
    """SS chính: ECAPA-TDNN."""
    return float(np.dot(ecapa_embedding(a), ecapa_embedding(b)))


@lru_cache(maxsize=1)
def _sv_model():
    from transformers import AutoFeatureExtractor, WavLMForXVector

    fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
    model = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").to(_device()).eval()
    return fe, model


@lru_cache(maxsize=4096)
def speaker_embedding(path: str) -> np.ndarray:
    import torch

    fe, model = _sv_model()
    wav, sr = load(path, sr=16000)
    inputs = fe(wav, sampling_rate=sr, return_tensors="pt").to(_device())
    with torch.inference_mode():
        emb = model(**inputs).embeddings[0]
    emb = torch.nn.functional.normalize(emb, dim=-1)
    return emb.cpu().numpy()


def speaker_similarity_wavlm(a: str, b: str) -> float:
    return float(np.dot(speaker_embedding(a), speaker_embedding(b)))


# ------------------------------------------------------------------ UTMOS
@lru_cache(maxsize=1)
def _utmos():
    import torch

    return torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True).to(_device()).eval()


def utmos(path: str) -> float:
    import torch

    wav, sr = load(path, sr=16000)
    with torch.inference_mode():
        return float(_utmos()(torch.from_numpy(wav)[None].to(_device()), sr))


# ------------------------------------------------------------------ emotion similarity
EMOTIONS = ("angry", "happy", "neutral", "sad", "surprised")
_EMO_ALIASES = {"anger": "angry", "happiness": "happy", "sadness": "sad", "surprise": "surprised"}


def norm_emotion(label: str | None) -> str | None:
    """'生气/angry', 'anger', 'Angry' -> 'angry'."""
    if not label:
        return None
    lab = label.split("/")[-1].strip().lower()
    return _EMO_ALIASES.get(lab, lab)


@lru_cache(maxsize=1)
def _emotion2vec():
    from funasr import AutoModel

    return AutoModel(model="emotion2vec/emotion2vec_plus_large", hub="hf", disable_update=True)


@lru_cache(maxsize=4096)
def _emotion_info(path: str) -> tuple[np.ndarray, str]:
    res = _emotion2vec().generate(path, granularity="utterance", extract_embedding=True)[0]
    v = np.asarray(res["feats"], dtype=np.float32).reshape(-1)
    scores = {norm_emotion(lab): sc for lab, sc in zip(res["labels"], res["scores"])}
    label = max(EMOTIONS, key=lambda e: scores.get(e, -1.0))   # chỉ xét 5 lớp của ESD
    return v / (np.linalg.norm(v) + 1e-9), label


def emotion_embedding(path: str) -> np.ndarray:
    return _emotion_info(path)[0]


def emotion_label(path: str) -> str:
    return _emotion_info(path)[1]


def emotion_similarity(a: str, b: str) -> float:
    return float(np.dot(emotion_embedding(a), emotion_embedding(b)))


def summarize(values: list[float]) -> dict:
    arr = np.array([v for v in values if v is not None and not np.isnan(v)], dtype=float)
    if not len(arr):
        return {"mean": None, "n": 0}
    return {"mean": round(float(arr.mean()), 4), "std": round(float(arr.std()), 4), "n": int(len(arr))}
