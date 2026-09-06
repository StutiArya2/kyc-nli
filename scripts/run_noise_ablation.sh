#!/usr/bin/env bash
# POSIX twin of run_noise_ablation.ps1. See that file for the rationale.
set -euo pipefail
export PYTHONIOENCODING=utf-8

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
python="$root/.venv/bin/kyc-nli"
[ -x "$python" ] || python="$root/.venv/Scripts/kyc-nli.exe"

for noise in clean light moderate heavy; do
  echo ""
  echo "=== noise = $noise ==="
  "$python" generate --identities 120 --noise "$noise" --seed 20260906 \
      --out "data/processed/abl_$noise.jsonl" > /dev/null
  "$python" compare --dataset "data/processed/abl_$noise.test.jsonl"
done
