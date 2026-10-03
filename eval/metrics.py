"""Các chỉ số đánh giá. Mô hình chấm điểm nạp lười, một lần mỗi tiến trình.

| Chỉ số  | Mô hình                                   |
| CER/WER | ASR tiếng Việt: parakeet-ctc-0.6b-vi / Whisper large-v3 |
| SS      | WavLM-base-plus-sv (cosine x-vector)      |
| UTMOS   | SpeechMOS utmos22_strong (huấn luyện chủ yếu trên tiếng Anh — ghi hạn chế) |
| ES      | emotion2vec (cosine embedding câu gốc ↔ câu lồng tiếng) |
"""

from __future__ import annotations

from functools import lru_cache

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
@lru_cache(maxsize=1)
def _sv_model():
    from transformers import AutoFeatureExtractor, WavLMForXVector

    fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
    model = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").to(_device()).eval()
    return fe, model


def speaker_embedding(path: str) -> np.ndarray:
    import torch

    fe, model = _sv_model()
    wav, sr = load(path, sr=16000)
    inputs = fe(wav, sampling_rate=sr, return_tensors="pt").to(_device())
    with torch.inference_mode():
        emb = model(**inputs).embeddings[0]
    emb = torch.nn.functional.normalize(emb, dim=-1)
    return emb.cpu().numpy()


def speaker_similarity(a: str, b: str) -> float:
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
@lru_cache(maxsize=1)
def _emotion2vec():
    from funasr import AutoModel

    return AutoModel(model="iic/emotion2vec_plus_large", disable_update=True)


def emotion_embedding(path: str) -> np.ndarray:
    res = _emotion2vec().generate(path, granularity="utterance", extract_embedding=True)
    v = np.asarray(res[0]["feats"], dtype=np.float32).reshape(-1)
    return v / (np.linalg.norm(v) + 1e-9)


def emotion_similarity(a: str, b: str) -> float:
    return float(np.dot(emotion_embedding(a), emotion_embedding(b)))


def summarize(values: list[float]) -> dict:
    arr = np.array([v for v in values if v is not None and not np.isnan(v)], dtype=float)
    if not len(arr):
        return {"mean": None, "n": 0}
    return {"mean": round(float(arr.mean()), 4), "std": round(float(arr.std()), 4), "n": int(len(arr))}
