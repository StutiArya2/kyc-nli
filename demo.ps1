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

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

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

& $exe demo --step $Step --bootstrap $Bootstrap
