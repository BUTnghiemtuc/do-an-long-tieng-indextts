#!/usr/bin/env bash
# Chờ Run 1 xong, rồi đo VRAM đỉnh + tốc độ của 4 cấu hình trên 1000 cặp dài nhất (trường hợp xấu nhất).
# Batch hiệu dụng luôn = 32, nên kết quả học không đổi. Ghi cấu hình chọn được vào data/best_batch.txt.
set -uo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub TORCH_HOME=$PWD/.cache/torch PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/thor/miniconda3/envs/vidub/bin/python
while tmux has-session -t run1 2>/dev/null; do sleep 60; done
LIMIT=11.5
echo "bs accum gc max_vram_gb s_per_step" > logs/bench_vram.txt
for cfg in "8 4 true" "16 2 true" "8 4 false" "16 2 false" "32 1 false"; do
  set -- $cfg; out=runs/bench_${1}_${2}_${3}; rm -rf $out
  $PY -m training.indextts25.train -c training/indextts25/config_vi.yaml \
      --set data.train_pairs=data/features/bench_longest.jsonl --set data.dev_pairs=null \
      --set train.batch_size=$1 --set train.gradient_accumulation=$2 --set train.gradient_checkpointing=$3 \
      --set train.max_steps=12 --set run.log_every=2 --set run.tensorboard=false --set run.output_dir=$out \
      > $out.log 2>&1
  $PY - "$out" "$1 $2 $3" >> logs/bench_vram.txt <<'PYEOF'
import json, sys
rs = [json.loads(l) for l in open(sys.argv[1] + "/log.jsonl")] if __import__("os").path.exists(sys.argv[1] + "/log.jsonl") else []
rs = [r for r in rs if "elapsed_s" in r]
if len(rs) < 3 or rs[-1]["step"] < 12:
    print(sys.argv[2], "OOM/lỗi", "-")
else:
    a, b = rs[1], rs[-1]
    print(sys.argv[2], max(r["max_vram_gb"] for r in rs), round((b["elapsed_s"] - a["elapsed_s"]) / (b["step"] - a["step"]), 3))
PYEOF
  rm -rf $out/*.pt
done
# chọn cấu hình nhanh nhất có VRAM đỉnh <= LIMIT
awk -v L=$LIMIT 'NR>1 && $4!="OOM/lỗi" && $4+0<=L {print $5, $1, $2, $3, $4}' logs/bench_vram.txt | sort -n | head -1 > data/best_batch.txt
cat logs/bench_vram.txt; echo "CHỌN (s/bước bs accum gc vram):"; cat data/best_batch.txt
