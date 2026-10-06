# Build dist\Typeless\Typeless.exe (PyInstaller) and dist\TypelessSetup.exe (Inno Setup).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$python = ".\.venv\python.exe"
$version = (& $python -c "import typeless; print(typeless.__version__)").Trim()
Write-Host "Typeless $version"

& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "tests failed" }

& $python scripts\make_icon.py
# Pre-generate the UI Automation COM wrappers so the frozen app doesn't need to.
& $python -c "import comtypes.client; comtypes.client.GetModule('UIAutomationCore.dll')"

& $python -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name Typeless `
    --icon packaging\typeless.ico `
    --collect-all faster_whisper `
    --collect-all ctranslate2 `
    --collect-binaries onnxruntime `
    --collect-data onnxruntime `
    --collect-all _sounddevice_data `
    --collect-submodules comtypes.gen `
    --hidden-import comtypes.gen.UIAutomationClient `
    --exclude-module pytest `
    run.pyw
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup not found: winget install JRSoftware.InnoSetup" }
# Windows Defender sometimes scans the fresh setup exe while Inno writes its icon
# ("EndUpdateResource failed"); a retry a few seconds later succeeds.
foreach ($attempt in 1..3) {
    & $iscc /Q "/DAppVersion=$version" packaging\typeless.iss
    if ($LASTEXITCODE -eq 0) { break }
    if ($attempt -eq 3) { throw "Inno Setup failed" }
    Write-Host "Inno Setup failed (attempt $attempt), retrying..."
    Start-Sleep -Seconds 5
}
Write-Host "Done: dist\TypelessSetup-$version.exe"
