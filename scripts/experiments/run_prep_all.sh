#!/usr/bin/env bash
# Mục 5.2 -> 6 cho cả 3 bộ (ViMD đã lọc sẵn ở data/clean/vimd.jsonl)
set -euo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
PY=/home/thor/miniconda3/envs/vidub/bin/python
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub HF_DATASETS_CACHE=$PWD/.cache/huggingface/datasets TORCH_HOME=$PWD/.cache/torch
$PY -m data_prep.filter data/raw/vivoice/raw.jsonl data/clean/vivoice.jsonl
$PY -m data_prep.filter data/raw/phoaudiobook/raw.jsonl data/clean/phoaudiobook.jsonl --max-cer 0.05
$PY -m data_prep.split data/clean/vimd.jsonl data/clean/vivoice.jsonl data/clean/phoaudiobook.jsonl data/splits --test-speakers 25
$PY -m data_prep.stats data/splits/train.jsonl --md docs/data_stats.md
$PY -m training.indextts25.prepare_features data/splits/train.jsonl data/features/train \
    --model-dir checkpoints/IndexTTS-2.5 --split-name train
$PY -m training.indextts25.prepare_features data/splits/dev.jsonl data/features/dev \
    --model-dir checkpoints/IndexTTS-2.5 --split-name dev
echo "PREP XONG"
