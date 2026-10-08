"""Nạp cấu hình YAML, gộp nhiều file và ghi đè từng khoá bằng `a.b=c`."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"
ENV_FILE = DEFAULT_CONFIG.parent.parent / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Nạp KEY=VALUE từ .env (khoá API). Biến môi trường đã đặt sẵn luôn được ưu tiên."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def parse_override(item: str) -> dict:
    """`synthesize.backend=mock` -> {"synthesize": {"backend": "mock"}}; giá trị đọc như YAML."""
    if "=" not in item:
        raise ValueError(f"Ghi đè phải có dạng khoa.con=gia_tri, nhận: {item!r}")
    path, raw = item.split("=", 1)
    value: Any = yaml.safe_load(raw)
    if isinstance(value, str):
        try:                      # YAML 1.1 đọc "5e-5" (không có dấu chấm) thành chuỗi
            value = float(value) if value.strip().lower() not in ("nan", "inf", "-inf", "infinity") else value
        except ValueError:
            pass
    node: dict = {}
    cur = node
    keys = path.strip().split(".")
    for k in keys[:-1]:
        cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value
    return node


def load_config(paths: list[str | Path] | None = None, overrides: list[str] | None = None) -> dict:
    load_env_file()
    cfg = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    for p in paths or []:
        cfg = deep_merge(cfg, yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {})
    for item in overrides or []:
        cfg = deep_merge(cfg, parse_override(item))
    return cfg
