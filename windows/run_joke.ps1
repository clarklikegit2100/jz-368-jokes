<#
.SYNOPSIS
  Send one Telegram joke for a time slot. Called by Windows Task Scheduler.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File windows\run_joke.ps1 -Phase morning
  powershell -NoProfile -ExecutionPolicy Bypass -File windows\run_joke.ps1 -Phase afternoon -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("morning", "afternoon", "evening")]
    [string]$Phase,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$LogDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("jokes-{0}.log" -f (Get-Date -Format "yyyy-MM"))

function Write-Log([string]$Text) {
    $line = "{0}  [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Phase, $Text
    Write-Output $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

# Load TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (and optional JOKE_PYTHON) from .env in the repo root.
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    foreach ($raw in Get-Content -Path $EnvFile -Encoding UTF8) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { continue }
        $name, $value = $line.Split("=", 2)
        $name = $name.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if ($name) { Set-Item -Path ("Env:" + $name) -Value $value }
    }
}

if (-not $DryRun) {
    foreach ($required in "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID") {
        $current = [Environment]::GetEnvironmentVariable($required)
        if (-not $current -or $current -like "replace_with*") {
            Write-Log "ERROR: $required is not set. Put it in $EnvFile (see .env.example)."
            exit 2
        }
    }
}

# Same slot -> language mapping as the GitHub Actions workflow (zh : en = 2 : 1).
switch ($Phase) {
    "afternoon" { $Csv = "daily-jokes-en-720.csv"; $Db = "data\jokes.db";    $State = "data\selection_state-en.json" }
    default     { $Csv = "daily-jokes-zh-500.csv"; $Db = "data\jokes-zh.db"; $State = "data\selection_state-zh.json" }
}

# Pick a Python: JOKE_PYTHON from .env, then the py launcher, then python on PATH.
$PythonCmd = @()
if ($env:JOKE_PYTHON) {
    $PythonCmd = @($env:JOKE_PYTHON)
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = @("py", "-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = @("python")
} else {
    Write-Log "ERROR: Python not found. Install Python 3 or set JOKE_PYTHON in .env to the full path of python.exe."
    exit 3
}

$env:PYTHONIOENCODING = "utf-8"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$PyArgs = @("send_telegram_joke.py", "--phase", $Phase, "--csv", $Csv, "--db", $Db, "--state", $State)
if ($DryRun) { $PyArgs += "--dry-run" }

$Exe = $PythonCmd[0]
$ExeArgs = @()
if ($PythonCmd.Count -gt 1) { $ExeArgs = $PythonCmd[1..($PythonCmd.Count - 1)] }
$ExeArgs += $PyArgs

Write-Log ("Running: {0} {1}" -f $Exe, ($ExeArgs -join " "))
$ErrorActionPreference = "Continue"
$output = & $Exe @ExeArgs 2>&1
$code = $LASTEXITCODE
foreach ($o in $output) { Write-Log ([string]$o) }
if ($code -ne 0) {
    Write-Log "FAILED with exit code $code"
    exit $code
}
Write-Log "OK"
exit 0
