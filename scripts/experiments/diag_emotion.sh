#!/usr/bin/env bash
# Chẩn đoán mất cảm xúc / giọng xuyên ngôn ngữ: sinh trên GPU (giới hạn VRAM, chạy cạnh Run 2), chấm trên CPU
set -uo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub TORCH_HOME=$PWD/.cache/torch PYTHONPATH=$PWD/third_party/index-tts
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/thor/miniconda3/envs/vidub/bin/python
T=data/esd_en/emotion_test.jsonl
gen() {  # tên, thư mục model, [--set thêm]
  local name=$1 dir=$2; shift 2
  $PY -m eval.eval_tts $T --name "$name" -c configs/indextts25_vi.yaml --set synthesize.indextts.model_dir="$dir" \
      --set synthesize.indextts.cfg_path="$dir/config.yaml" "$@" --generate-only --max-vram-frac 0.42
}
[ -f checkpoints/r2_028000/gpt.pth ] || $PY -m training.indextts25.export runs/run2/step_028000.pt --base-dir checkpoints/IndexTTS-2.5 --out checkpoints/r2_028000
gen emo_r1_lr5e-5_6000 checkpoints/r1_lr5e-5_6000
gen emo_r1_lr2e-5_9159 checkpoints/r1_lr2e-5_9159
gen emo_r2_028000 checkpoints/r2_028000
for n in emo_r1_lr5e-5_6000 emo_r1_lr2e-5_9159 emo_r2_028000; do
  CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=8 nice -n 10 $PY -m eval.eval_tts $T --name $n -c configs/indextts25_vi.yaml --es
done
$PY -m eval.eval_tts --compare results/tts/emo_*/summary.json
echo "DIAG XONG"
