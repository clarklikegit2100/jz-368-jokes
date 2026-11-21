<#
.SYNOPSIS
  Register three Windows Task Scheduler jobs that send the daily jokes.

.DESCRIPTION
  Creates tasks "JZ Jokes - morning", "JZ Jokes - afternoon", "JZ Jokes - evening" under the
  "\JZ Jokes\" folder. Times use this PC's local clock. Missed runs (PC asleep/off) run as soon as
  the PC is available again.

.EXAMPLE
  # Default times 08:00 / 12:30 / 20:00, runs while you are signed in:
  powershell -NoProfile -ExecutionPolicy Bypass -File windows\install_tasks.ps1

  # Custom times:
  powershell -NoProfile -ExecutionPolicy Bypass -File windows\install_tasks.ps1 -Morning 07:30 -Afternoon 12:00 -Evening 21:00

  # Also run when you are signed out (run from an Administrator PowerShell):
  powershell -NoProfile -ExecutionPolicy Bypass -File windows\install_tasks.ps1 -RunWhenSignedOut
#>
[CmdletBinding()]
param(
    [string]$Morning = "08:00",
    [string]$Afternoon = "12:30",
    [string]$Evening = "20:00",
    [switch]$RunWhenSignedOut
)

$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "run_joke.ps1"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path $Runner)) { throw "Cannot find $Runner" }

$TaskPath = "\JZ Jokes\"
$UserId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if ($RunWhenSignedOut) {
    # S4U: runs whether or not you are signed in, no stored password. Needs admin to register.
    $Principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType S4U -RunLevel Limited
} else {
    $Principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Limited
}

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

$Slots = [ordered]@{ morning = $Morning; afternoon = $Afternoon; evening = $Evening }
foreach ($phase in $Slots.Keys) {
    $time = [datetime]::ParseExact($Slots[$phase], "HH:mm", $null)
    $name = "JZ Jokes - $phase"
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument ("-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"{0}`" -Phase {1}" -f $Runner, $phase) `
        -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -Daily -At $time
    Register-ScheduledTask -TaskName $name -TaskPath $TaskPath -Action $action -Trigger $trigger `
        -Principal $Principal -Settings $Settings -Force `
        -Description "Send one $phase joke to Telegram (jz-368-jokes)." | Out-Null
    Write-Host ("Registered '{0}' daily at {1}" -f $name, $time.ToString("HH:mm"))
}

Write-Host ""
Write-Host "Done. Test one now with:"
Write-Host "  Start-ScheduledTask -TaskPath '$TaskPath' -TaskName 'JZ Jokes - morning'"
Write-Host "Logs: $RepoRoot\data\logs\"
