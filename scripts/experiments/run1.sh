#!/usr/bin/env bash
# Mục 8 — Run 1: 1 epoch, so 2 mức learning rate (cặp đã lọc theo độ giống giọng >= 0.5)
set -uo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub TORCH_HOME=$PWD/.cache/torch PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/thor/miniconda3/envs/vidub/bin/python
for lr in 5e-5 2e-5; do
  out=runs/run1_lr$lr
  last=$(ls $out/step_*.pt 2>/dev/null | tail -1)
  $PY -m training.indextts25.train -c training/indextts25/config_vi.yaml \
      --set train.epochs=1 --set train.learning_rate=$lr --set run.output_dir=$out ${last:+--resume $last}
done
echo "RUN1 XONG"
