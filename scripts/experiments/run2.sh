#!/usr/bin/env bash
# Chuẩn bị dữ liệu bổ sung -> chia tập lại -> trích đặc trưng phần mới -> ghép cặp (lọc giọng) -> Run 2
set -euo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub HF_DATASETS_CACHE=$PWD/.cache/huggingface/datasets TORCH_HOME=$PWD/.cache/torch
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/thor/miniconda3/envs/vidub/bin/python
step() { echo "=== $(date '+%F %T') $*"; }

step "lọc PhoAudiobook bổ sung"
[ -f data/clean/phoaudiobook_more.jsonl.done ] || { $PY -m data_prep.filter data/raw/phoaudiobook_more/raw.jsonl data/clean/phoaudiobook_more.jsonl --max-cer 0.05 && touch data/clean/phoaudiobook_more.jsonl.done; }

step "chờ tải xong viVoice bổ sung"
while tmux has-session -t vivoice2 2>/dev/null; do sleep 60; done
grep -aq "^Xong" logs/import_vivoice_more.log || { echo "tải viVoice bổ sung lỗi"; exit 1; }
step "lọc viVoice bổ sung"
[ -f data/clean/vivoice_more.jsonl.done ] || { $PY -m data_prep.filter data/raw/vivoice_more/raw.jsonl data/clean/vivoice_more.jsonl && touch data/clean/vivoice_more.jsonl.done; }

step "chia tập lại (5 manifest)"
[ -d data/splits_run1 ] || cp -r data/splits data/splits_run1
$PY -m data_prep.split data/clean/vimd.jsonl data/clean/vivoice.jsonl data/clean/vivoice_more.jsonl \
    data/clean/phoaudiobook.jsonl data/clean/phoaudiobook_more.jsonl data/splits --test-speakers 25
$PY -m data_prep.stats data/splits/train.jsonl --md docs/data_stats.md

step "trích đặc trưng (bỏ qua câu đã có)"
$PY -m training.indextts25.prepare_features data/splits/train.jsonl data/features/train --model-dir checkpoints/IndexTTS-2.5 --split-name train
$PY -m training.indextts25.prepare_features data/splits/dev.jsonl data/features/dev --model-dir checkpoints/IndexTTS-2.5 --split-name dev

step "ghép cặp, lọc theo độ giống giọng"
$PY -m training.indextts25.make_pairs data/splits/train.jsonl data/features/train/pairs_train.jsonl --features data/features/train --min-spk-sim 0.5
$PY -m training.indextts25.make_pairs data/splits/dev.jsonl data/features/dev/pairs_dev.jsonl \
    --prompt-manifest data/splits/train.jsonl --features data/features/train data/features/dev --min-spk-sim 0.5

step "Run 2: lr 5e-5 (thắng Run 1), 3 epoch"
last=$(ls runs/run2/step_*.pt 2>/dev/null | tail -1 || true)
$PY -m training.indextts25.train -c training/indextts25/config_vi.yaml --set train.learning_rate=5e-5 \
    --set run.eval_every=2000 --set run.keep_checkpoints=40 --set run.output_dir=runs/run2 ${last:+--resume $last}
step "RUN2 XONG"
