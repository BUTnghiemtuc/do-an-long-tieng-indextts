#!/usr/bin/env bash
# Chờ Run 1 xong -> xuất checkpoint -> chấm CER/SS/UTMOS trên dev_tts_v2 (100 câu) -> bảng so sánh
set -uo pipefail
cd /data_hdd/Vidub/do-an-long-tieng-indextts
export HF_HUB_CACHE=$PWD/.cache/huggingface/hub TORCH_HOME=$PWD/.cache/torch PYTHONPATH=$PWD/third_party/index-tts
PY=/home/thor/miniconda3/envs/vidub/bin/python
while tmux has-session -t run1 2>/dev/null; do sleep 30; done
ev() {  # tên, thư mục model
  $PY -m eval.eval_tts data/splits/dev_tts_v2.jsonl --name "$1" -c configs/indextts25_vi.yaml \
      --set synthesize.indextts.model_dir="$2" --set synthesize.indextts.cfg_path="$2/config.yaml"
}
for ck in run1_lr5e-5/step_009159 run1_lr5e-5/step_006000 run1_lr2e-5/step_009159; do
  name=r1_$(echo $ck | tr '/' '_' | sed 's/run1_//; s/step_00//')
  [ -f checkpoints/$name/gpt.pth ] || $PY -m training.indextts25.export runs/$ck.pt --base-dir checkpoints/IndexTTS-2.5 --out checkpoints/$name
  ev dev_$name checkpoints/$name
done
ev dev_base checkpoints/IndexTTS-2.5
$PY -m eval.eval_tts --compare results/tts/dev_*/summary.json
echo "EVAL RUN1 XONG"
