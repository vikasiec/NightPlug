# NightPlug one-shot demo
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -e .
}
.\.venv\Scripts\python.exe -m nightplug demo
Write-Host ""
Write-Host "Open the HTML file under reports\"
