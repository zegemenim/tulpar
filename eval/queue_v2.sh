#!/bin/sh
# Modeller indikçe sırayla değerlendir
cd ~/tulpar/eval
M=~/tulpar/models
run() { until journalctl -t tulpar --no-pager | grep -q "model indi: $2"; do sleep 30; done; python3 run_eval_v2.py "$1" "$M/$2"; }
python3 run_eval_v2.py qwen35-9b "$M/Qwen3.5-9B-Q8_0.gguf"
run gemma4-26b-q3 gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf
run qwen36-35b-iq3 Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf
run qwen36-35b-q4 Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
logger -t tulpar "tum v2 testleri tamam"
