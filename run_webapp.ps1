param(
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendRoot = Join-Path $ProjectRoot "frontend"
Set-Location $ProjectRoot

$preferredPython = @(
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($preferredPython) {
    $python = $preferredPython
} elseif ($pythonCommand -and $pythonCommand.Source -notmatch "WindowsApps") {
    $python = $pythonCommand.Source
} else {
    throw "Python sebenar tidak ditemui. Pasang Python 3.10+ atau tambah Python ke PATH."
}

& $python -m pip install -r requirements.txt
if (-not (Test-Path (Join-Path $FrontendRoot "node_modules"))) {
    Push-Location $FrontendRoot
    npm.cmd install
    Pop-Location
}

$apiCommand = "& '$python' -m uvicorn api:app --host 127.0.0.1 --port $ApiPort"
$frontendCommand = "set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$ApiPort&& npm.cmd run dev -- -p $FrontendPort"

Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-Command", $apiCommand -WorkingDirectory $ProjectRoot -WindowStyle Hidden
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $frontendCommand -WorkingDirectory $FrontendRoot -WindowStyle Hidden

Write-Host "FastAPI:  http://127.0.0.1:$ApiPort"
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
