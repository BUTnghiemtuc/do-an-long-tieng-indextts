#!/usr/bin/env bash
# (1) Thử tham số giải mã trên dev cho Run 2 bước 28000 (không cần train) + đo nhiễu (chạy lặp cấu hình hiện tại)
# (2) Run 3 thử nghiệm lần 2: cảm xúc 100% từ câu đích (p=1.0), để xem hiệu ứng có tăng theo p không
set -uo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub TORCH_HOME=$PWD/.cache/torch PYTHONPATH=$PWD/third_party/index-tts
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/thor/miniconda3/envs/vidub/bin/python
step() { echo "=== $(date '+%F %T') $*"; }
M=checkpoints/r2_028000
ev() { local set=$1 name=$2 dir=$3; shift 3
  $PY -m eval.eval_tts "$set" --name "$name" -c configs/indextts25_vi.yaml \
      --set synthesize.indextts.model_dir="$dir" --set synthesize.indextts.cfg_path="$dir/config.yaml" "$@"; }

step "giải mã: lặp cấu hình hiện tại (đo nhiễu) + temperature thấp hơn + beam"
ev data/splits/dev_tts_v3.jsonl dec_r2_T0.7_rep $M
ev data/splits/dev_tts_v3.jsonl dec_r2_T0.5 $M --set synthesize.indextts.generation.temperature=0.5
ev data/splits/dev_tts_v3.jsonl dec_r2_T0.3 $M --set synthesize.indextts.generation.temperature=0.3
ev data/splits/dev_tts_v3.jsonl dec_r2_T0.7_beam3 $M --set synthesize.indextts.generation.num_beams=3
$PY -m eval.eval_tts --compare results/tts/dev3_r2_028000/summary.json results/tts/dec_*/summary.json

step "Run 3 thử nghiệm lần 2 (p=1.0)"
last=$(ls runs/run3_pilot_p1/step_*.pt 2>/dev/null | tail -1 || true)
$PY -m training.indextts25.train -c training/indextts25/config_vi.yaml --set train.learning_rate=5e-5 \
    --set train.emotion_from_target_prob=1.0 --set train.max_steps=9200 --set run.eval_every=2000 \
    --set run.output_dir=runs/run3_pilot_p1 ${last:+--resume $last}
[ -f checkpoints/r3p1_9200/gpt.pth ] || $PY -m training.indextts25.export runs/run3_pilot_p1/step_009200.pt \
    --base-dir checkpoints/IndexTTS-2.5 --out checkpoints/r3p1_9200
ev data/esd_en/emotion_test.jsonl emo_r3p1_9200 checkpoints/r3p1_9200 --es
ev data/splits/dev_tts_v3.jsonl dev3_r3p1_9200 checkpoints/r3p1_9200
$PY -m eval.eval_tts --compare results/tts/emo_r*/summary.json results/tts/dev3_r*/summary.json
step "SWEEP+PILOT2 XONG"
