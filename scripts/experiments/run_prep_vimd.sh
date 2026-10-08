#!/usr/bin/env bash
# Chờ import ViMD xong rồi chạy mục 5.2 -> 6 của docs/huong-dan-may-gpu.md
set -euo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
PY=/home/thor/miniconda3/envs/vidub/bin/python
# model/cache tải về nằm trong dự án (trên /data_hdd), không ghi vào ~/.cache
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub HF_DATASETS_CACHE=$PWD/.cache/huggingface/datasets TORCH_HOME=$PWD/.cache/torch
while tmux has-session -t vimd 2>/dev/null; do sleep 60; done
grep -q "^Xong:" logs/import_vimd.log || { echo "import ViMD chưa xong/bị lỗi"; exit 1; }
mkdir -p data/clean
$PY -m data_prep.filter data/raw/vimd/raw.jsonl data/clean/vimd.jsonl
$PY -m data_prep.split data/clean/vimd.jsonl data/splits --test-speakers 25
$PY -m data_prep.stats data/splits/train.jsonl --md docs/data_stats.md
$PY -m training.indextts25.prepare_features data/splits/train.jsonl data/features/train \
    --model-dir checkpoints/IndexTTS-2.5 --split-name train
$PY -m training.indextts25.prepare_features data/splits/dev.jsonl data/features/dev \
    --model-dir checkpoints/IndexTTS-2.5 --split-name dev
echo "PREP XONG"
