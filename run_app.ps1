param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
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
    throw "Python sebenar tidak ditemui. Windows hanya menunjukkan Microsoft Store alias. Pasang Python 3.10+ atau tambah Python ke PATH."
}

& $python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
& $python -m streamlit run app.py --server.port $Port
