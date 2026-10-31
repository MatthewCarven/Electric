<#
.SYNOPSIS
    Build Electric as a Windows app (.exe), a screensaver (.scr), or both.

.DESCRIPTION
    Both come from the same source through PyInstaller, each one
    self-contained file dropped in this folder:

      Electric.exe   the app (main.py): double-click it to run Electric in a
                     window with its settings panel. Takes every command-line
                     option too (Electric.exe --help from a terminal).
      Electric.scr   the screensaver (screensaver.py): answers Windows' /s /p
                     /c. Right-click it > Install. Its Settings button opens the
                     same panel, and Save there is what the screensaver reads.

    Both read and write the same config.json (%APPDATA%\Electric\config.json).

    One-time prerequisite: python -m pip install -r requirements.txt
    PyInstaller is installed for you if it is missing.

.PARAMETER Target
    all (default), app, or screensaver.

.PARAMETER Python
    The Python to build with. Defaults to "python" on PATH.

.EXAMPLE
    pwsh -File build.ps1
    Builds both.
#>
param(
    [ValidateSet("all", "app", "screensaver")]
    [string]$Target = "all",
    [string]$Python = "python"
)

# Native tools are checked through $LASTEXITCODE: PyInstaller logs to stderr.
Set-Location -LiteralPath $PSScriptRoot
$env:PYGAME_HIDE_SUPPORT_PROMPT = "1"

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "BUILD FAILED: $Message" -ForegroundColor Red
    exit 1
}

function Test-Import([string]$Module) {
    & $Python -c "import $Module" *> $null
    return $LASTEXITCODE -eq 0
}

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    Fail "can't find '$Python'. Install Python, or pass -Python <path to python.exe>."
}
$missing = @("pygame", "moderngl", "glcontext") | Where-Object { -not (Test-Import $_) }
if ($missing) {
    Fail ("missing " + ($missing -join ", ") + ". Run once:  $Python -m pip install -r requirements.txt")
}
if (-not (Test-Import "PyInstaller")) {
    Write-Host "PyInstaller isn't installed; installing it now..."
    & $Python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { Fail "couldn't install PyInstaller." }
}

# The icon is a real render, made fresh each build.
$icon = Join-Path $PSScriptRoot "build\electric.ico"
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot "build") | Out-Null
& $Python (Join-Path $PSScriptRoot "tools\make_icon.py") $icon
if ($LASTEXITCODE -ne 0) { Fail "couldn't render the icon." }

function Build-Target([string]$Kind, [string]$Script, [string]$Output) {
    $dist = Join-Path $PSScriptRoot "dist\$Kind"
    $work = Join-Path $PSScriptRoot "build\$Kind"
    Write-Host ""
    Write-Host "=== Building $Output from $Script ===" -ForegroundColor Cyan
    $started = Get-Date

    # --collect-data electric : the GLSL shaders live beside the code
    # glcontext               : moderngl imports it only when making a context
    # numpy, tkinter          : installed here, never used; keeps the file small
    $pyiArgs = @(
        "-m", "PyInstaller", "--noconfirm", "--log-level", "WARN",
        "--onefile", "--windowed", "--name", "Electric", "--icon", $icon,
        "--collect-submodules", "electric", "--collect-data", "electric",
        "--hidden-import", "glcontext", "--collect-submodules", "glcontext",
        "--exclude-module", "numpy", "--exclude-module", "tkinter",
        "--distpath", $dist, "--workpath", $work, "--specpath", $work,
        (Join-Path $PSScriptRoot $Script)
    )
    & $Python @pyiArgs
    if ($LASTEXITCODE -ne 0) { Fail "PyInstaller couldn't build $Output (exit code $LASTEXITCODE)." }

    try {
        Copy-Item -LiteralPath (Join-Path $dist "Electric.exe") `
                  -Destination (Join-Path $PSScriptRoot $Output) -Force -ErrorAction Stop
    } catch {
        Fail "built, but couldn't copy it to $Output. Is it running? Close it and build again. ($($_.Exception.Message))"
    }
    $seconds = [int]((Get-Date) - $started).TotalSeconds
    Write-Host "Built $Output in $seconds s."
}

$built = @()
if ($Target -in "all", "app") {
    Build-Target "app" "main.py" "Electric.exe"
    $built += "Electric.exe"
}
if ($Target -in "all", "screensaver") {
    Build-Target "screensaver" "screensaver.py" "Electric.scr"
    $built += "Electric.scr"
}

Write-Host ""
Write-Host "Done:" -ForegroundColor Green
foreach ($name in $built) {
    $mb = "{0,6:N1} MB" -f ((Get-Item -LiteralPath (Join-Path $PSScriptRoot $name)).Length / 1MB)
    Write-Host "  $name  $mb"
}
Write-Host ""
if ($built -contains "Electric.exe") {
    Write-Host "App:          double-click Electric.exe. H shows/hides the settings panel,"
    Write-Host "              F goes fullscreen, Save settings keeps them for the screensaver."
}
if ($built -contains "Electric.scr") {
    Write-Host "Screensaver:  right-click Electric.scr in Explorer > Install."
}
