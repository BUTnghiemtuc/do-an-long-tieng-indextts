#!/usr/bin/env bash
# Run 3 thử nghiệm: vector cảm xúc từ câu đích (p=0.5). Chờ Run 2 + eval2 xong, train ~9.200 bước (= Run 1),
# rồi chấm test cảm xúc ESD và dev; so với Run 1 / Run 2.
set -uo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub TORCH_HOME=$PWD/.cache/torch PYTHONPATH=$PWD/third_party/index-tts
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/thor/miniconda3/envs/vidub/bin/python
step() { echo "=== $(date '+%F %T') $*"; }
while tmux has-session -t run2 2>/dev/null || tmux has-session -t eval2 2>/dev/null; do sleep 60; done

step "train Run 3 thử nghiệm"
last=$(ls runs/run3_pilot/step_*.pt 2>/dev/null | tail -1 || true)
$PY -m training.indextts25.train -c training/indextts25/config_vi.yaml --set train.learning_rate=5e-5 \
    --set train.emotion_from_target_prob=0.5 --set train.max_steps=9200 --set run.eval_every=2000 \
    --set run.output_dir=runs/run3_pilot ${last:+--resume $last}
[ -f checkpoints/r3p_9200/gpt.pth ] || $PY -m training.indextts25.export runs/run3_pilot/step_009200.pt \
    --base-dir checkpoints/IndexTTS-2.5 --out checkpoints/r3p_9200

step "chấm"
for t in "data/esd_en/emotion_test.jsonl emo_r3p_9200 --es" "data/splits/dev_tts_v3.jsonl dev3_r3p_9200"; do
  set -- $t; ts=$1 name=$2; shift 2
  $PY -m eval.eval_tts $ts --name $name -c configs/indextts25_vi.yaml --set synthesize.indextts.model_dir=checkpoints/r3p_9200 \
      --set synthesize.indextts.cfg_path=checkpoints/r3p_9200/config.yaml "$@"
done
$PY -m eval.eval_tts --compare results/tts/emo_*/summary.json results/tts/dev3_*/summary.json
step "PILOT XONG"
