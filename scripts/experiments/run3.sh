#!/usr/bin/env bash
# Run 3: như Run 2 nhưng vector cảm xúc lấy 100% từ câu đích (emotion_from_target_prob=1.0)
# -> chấm checkpoint trên dev + test cảm xúc -> chọn -> test zero-shot -> results/tts/report_run3.md
set -uo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub TORCH_HOME=$PWD/.cache/torch PYTHONPATH=$PWD/third_party/index-tts
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/thor/miniconda3/envs/vidub/bin/python
step() { echo "=== $(date '+%F %T') $*"; }
ev() { local set=$1 name=$2 dir=$3; shift 3
  $PY -m eval.eval_tts "$set" --name "$name" -c configs/indextts25_vi.yaml \
      --set synthesize.indextts.model_dir="$dir" --set synthesize.indextts.cfg_path="$dir/config.yaml" "$@"; }

step "train Run 3"
last=$(ls runs/run3/step_*.pt 2>/dev/null | tail -1 || true)
$PY -m training.indextts25.train -c training/indextts25/config_vi.yaml --set train.learning_rate=5e-5 \
    --set train.emotion_from_target_prob=1.0 --set run.eval_every=2000 --set run.keep_checkpoints=40 \
    --set run.output_dir=runs/run3 ${last:+--resume $last} || exit 1

step "chấm checkpoint (từ bước 24000, mỗi 8000, cộng bước cuối) trên dev + test cảm xúc"
lastck=$(ls runs/run3/step_*.pt | tail -1 | sed 's/.*step_//; s/\.pt//')
for s in $(ls runs/run3/step_*.pt | sed 's/.*step_//; s/\.pt//'); do
  n=$((10#$s))
  if { [ $n -ge 24000 ] && [ $(((n - 24000) % 8000)) -eq 0 ]; } || [ "$s" = "$lastck" ]; then
    [ -f checkpoints/r3_$s/gpt.pth ] || $PY -m training.indextts25.export runs/run3/step_$s.pt --base-dir checkpoints/IndexTTS-2.5 --out checkpoints/r3_$s
    ev data/splits/dev_tts_v3.jsonl dev3_r3_$s checkpoints/r3_$s
    ev data/esd_en/emotion_test.jsonl emo_r3_$s checkpoints/r3_$s --es
  fi
done
# chọn: CER dev thấp nhất trong các checkpoint có tỉ lệ đúng cảm xúc >= (tốt nhất - 5 điểm)
best=$($PY - <<'PYEOF'
import json, glob
c = {}
for p in glob.glob("results/tts/dev3_r3_*/summary.json"):
    s = p.split("dev3_r3_")[1].split("/")[0]
    try: e = json.load(open(f"results/tts/emo_r3_{s}/summary.json"))["emo_match"]["mean"]
    except FileNotFoundError: continue
    c[s] = (json.load(open(p))["cer"]["mean"], e)
top = max(e for _, e in c.values())
print(min((s for s in c if c[s][1] >= top - 0.05), key=lambda s: c[s][0]))
PYEOF
)
step "chọn bước $best"; echo "$best" > results/tts/run3_best_step.txt
ev data/splits/test_zeroshot.jsonl test_r3_$best checkpoints/r3_$best
{
  echo "# Kết quả Run 3 (cảm xúc từ câu đích; chọn bước $best)"
  echo; echo "## Dev"; echo; $PY -m eval.eval_tts --compare results/tts/dev3_r2_028000/summary.json results/tts/dev3_r3_*/summary.json
  echo; echo "## Chuyển cảm xúc"; echo; $PY -m eval.eval_tts --compare results/tts/emo_base/summary.json results/tts/emo_dinhthuan/summary.json results/tts/emo_r2_028000/summary.json results/tts/emo_r3*/summary.json
  echo; echo "## Test zero-shot"; echo; $PY -m eval.eval_tts --compare results/tts/test_*/summary.json
} > results/tts/report_run3.md
cat results/tts/report_run3.md
step "RUN3 XONG"
