# One-command demo launcher. See docs/DEMO.md for what each section says.
#
#   .\demo.ps1                 the full walkthrough, ~1 minute
#   .\demo.ps1 -Step 4         just the scoreboard
#   .\demo.ps1 -Bootstrap 1000 with full confidence intervals, ~20s slower
#
# The UTF-8 lines are not optional: without them Windows PowerShell renders
# Devanagari, Tamil, Bengali and Urdu as boxes, which is fatal for a demo whose
# first slide is a Bengali surname.

param(
    [int]$Step = 0,
    [int]$Bootstrap = 300
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# transformers prints a weight-loading progress bar and a load report to stderr.
# Two consequences, both fatal to a live demo and both handled here:
#   * with $ErrorActionPreference = "Stop", PowerShell turns any native-command
#     stderr into a terminating NativeCommandError -- the demo died on a
#     progress bar. So the preference is deliberately NOT "Stop" here; the exit
#     code is checked explicitly at the end instead.
#   * the report itself is noise on a projector.
$ErrorActionPreference = "Continue"
$env:TRANSFORMERS_VERBOSITY = "error"
$env:HF_HUB_DISABLE_PROGRESS_BARS = "1"

$exe = Join-Path $root ".venv\Scripts\kyc-nli.exe"
if (-not (Test-Path $exe)) {
    Write-Host "No virtualenv found. Set one up first:" -ForegroundColor Yellow
    Write-Host '  python -m venv .venv'
    Write-Host '  .\.venv\Scripts\python -m pip install -e ".[dev]"'
    exit 1
}

if ($Host.UI.RawUI.WindowSize.Width -lt 100) {
    Write-Host "Terminal is $($Host.UI.RawUI.WindowSize.Width) columns; widen past 100 or the tables wrap." -ForegroundColor Yellow
    Write-Host ""
}

& $exe demo --step $Step --bootstrap $Bootstrap 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "The demo exited with code $LASTEXITCODE. Re-run showing errors:" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\kyc-nli.exe demo --step $Step --bootstrap $Bootstrap"
    exit $LASTEXITCODE
}
