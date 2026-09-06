# Reproduces the noise-ablation table in README.md and docs/plan.md.
# Usage:  .\scripts\run_noise_ablation.ps1
#
# Regenerates the benchmark at each noise level and runs every baseline on it.
# Nothing here is hand-edited; if the table in the README disagrees with this
# script's output, the README is stale.

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\kyc-nli.exe"
$identities = 120
$seed = 20260906

foreach ($noise in @("clean", "light", "moderate", "heavy")) {
    Write-Host "`n=== noise = $noise ===" -ForegroundColor Cyan
    & $python generate --identities $identities --noise $noise --seed $seed `
        --out "data/processed/abl_$noise.jsonl" | Out-Null
    & $python compare --dataset "data/processed/abl_$noise.test.jsonl"
}

Write-Host "`nDone. Datasets are gitignored; copy the numbers into docs/plan.md by hand only if the table there is out of date." -ForegroundColor Green
