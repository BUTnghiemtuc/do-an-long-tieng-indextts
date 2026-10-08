#!/usr/bin/env bash
# Mục 9: chờ Run 2 xong -> chấm các checkpoint trên dev -> chọn theo CER -> test zero-shot + test cảm xúc
# so với IndexTTS 2.5 gốc, Run 1 và dinhthuan -> results/tts/report_run2.md
set -uo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub TORCH_HOME=$PWD/.cache/torch PYTHONPATH=$PWD/third_party/index-tts
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/thor/miniconda3/envs/vidub/bin/python
step() { echo "=== $(date '+%F %T') $*"; }

while tmux has-session -t run2 2>/dev/null; do sleep 60; done
grep -aq "RUN2 XONG" logs/run2.log || { echo "Run 2 chưa xong hoặc lỗi"; exit 1; }

step "bộ dev theo lần chia tập mới (câu mẫu cùng giọng)"
$PY - <<'EOF'
import json
man = {}
for f in ["data/splits/train.jsonl", "data/splits/dev.jsonl"]:
    for l in open(f):
        r = json.loads(l); man[r["id"]] = r
seen, rows = set(), []
for l in open("data/features/dev/pairs_dev.jsonl"):
    p = json.loads(l)
    if p["target"] in seen:
        continue
    seen.add(p["target"]); t, pr = man[p["target"]], man[p["prompt"]]
    rows.append({"id": t["id"], "text": t.get("text_norm") or t["text"], "speaker": t["speaker"],
                 "prompt_audio": pr["audio"], "ref_audio": t["audio"]})
with open("data/splits/dev_tts_v3.jsonl", "w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(rows), "câu dev")
EOF

ev() {  # testset, tên, thư mục model, [cờ thêm]
  local set=$1 name=$2 dir=$3; shift 3
  $PY -m eval.eval_tts "$set" --name "$name" -c configs/indextts25_vi.yaml \
      --set synthesize.indextts.model_dir="$dir" --set synthesize.indextts.cfg_path="$dir/config.yaml" "$@"
}
export_ck() {  # step -> checkpoints/r2_<step>
  [ -f "checkpoints/r2_$1/gpt.pth" ] || $PY -m training.indextts25.export "runs/run2/step_$1.pt" \
      --base-dir checkpoints/IndexTTS-2.5 --out "checkpoints/r2_$1"
}

step "chấm checkpoint Run 2 trên dev (từ bước 24000, mỗi 4000, cộng bước cuối)"
last=$(ls runs/run2/step_*.pt | tail -1 | sed 's/.*step_//; s/\.pt//')
for s in $(ls runs/run2/step_*.pt | sed 's/.*step_//; s/\.pt//'); do
  n=$((10#$s))
  if { [ $n -ge 24000 ] && [ $((n % 4000)) -eq 0 ]; } || [ "$s" = "$last" ]; then
    export_ck "$s" && ev data/splits/dev_tts_v3.jsonl "dev3_r2_$s" "checkpoints/r2_$s"
  fi
done
ev data/splits/dev_tts_v3.jsonl dev3_r1_lr5e-5_9159 checkpoints/r1_lr5e-5_9159
ev data/splits/dev_tts_v3.jsonl dev3_base checkpoints/IndexTTS-2.5

best=$($PY - <<'EOF'
import json, glob
s = [json.load(open(p)) for p in glob.glob("results/tts/dev3_r2_*/summary.json")]
b = min(s, key=lambda x: (x["cer"]["mean"], -x["ss"]["mean"]))
print(b["name"].replace("dev3_r2_", ""))
EOF
)
step "checkpoint tốt nhất theo CER dev: $best"
echo "$best" > results/tts/run2_best_step.txt

step "test zero-shot (25 người nói chưa nghe)"
ev data/splits/test_zeroshot.jsonl "test_r2_$best" "checkpoints/r2_$best"
ev data/splits/test_zeroshot.jsonl test_base checkpoints/IndexTTS-2.5
ev data/splits/test_zeroshot.jsonl test_r1_lr5e-5_9159 checkpoints/r1_lr5e-5_9159
$PY -m eval.eval_tts data/splits/test_zeroshot.jsonl --name test_dinhthuan -c configs/gpu.yaml

step "test chuyển cảm xúc (ESD tiếng Anh -> tiếng Việt)"
ev data/esd_en/emotion_test.jsonl "emo_r2_$best" "checkpoints/r2_$best" --es
$PY -m eval.eval_tts data/esd_en/emotion_test.jsonl --name emo_dinhthuan -c configs/gpu.yaml --es

step "bảng tổng hợp"
{
  echo "# Kết quả Run 2 (checkpoint chọn theo CER dev: bước $best)"
  echo; echo "## Dev (100 câu, người nói đã có trong train)"; echo
  $PY -m eval.eval_tts --compare results/tts/dev3_*/summary.json
  echo; echo "## Test zero-shot (180 câu, 25 người nói chưa nghe; Run 1 có thể đã nghe một phần)"; echo
  $PY -m eval.eval_tts --compare results/tts/test_*/summary.json
  echo; echo "## Chuyển cảm xúc (86 câu mẫu ESD tiếng Anh, 5 cảm xúc)"; echo
  $PY -m eval.eval_tts --compare results/tts/emo_*/summary.json
} > results/tts/report_run2.md
cat results/tts/report_run2.md
step "EVAL RUN2 XONG"
