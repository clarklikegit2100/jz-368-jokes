<#
.SYNOPSIS
  Register the Windows Task Scheduler job that sends the daily project report.

.DESCRIPTION
  Creates "\JZ Projects\JZ Projects - daily report", daily at 07:30 local time by default.
  A missed run (PC asleep/off) starts as soon as the PC is available again.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File project_agent\windows\install_report_task.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File project_agent\windows\install_report_task.ps1 -At 07:00
  # Also run when signed out (from an Administrator PowerShell):
  powershell -NoProfile -ExecutionPolicy Bypass -File project_agent\windows\install_report_task.ps1 -RunWhenSignedOut
#>
[CmdletBinding()]
param(
    [string]$At = "07:30",
    [switch]$RunWhenSignedOut
)

$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "run_report.ps1"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path $Runner)) { throw "Cannot find $Runner" }

$TaskPath = "\JZ Projects\"
$TaskName = "JZ Projects - daily report"
$UserId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if ($RunWhenSignedOut) {
    $Principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType S4U -RunLevel Limited
} else {
    $Principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Limited
}

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

$time = [datetime]::ParseExact($At, "HH:mm", $null)
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ("-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"{0}`"" -f $Runner) `
    -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $time
Register-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Action $action -Trigger $trigger `
    -Principal $Principal -Settings $Settings -Force `
    -Description "Send the daily GitHub project status report to Telegram (jz-368-jokes\project_agent)." | Out-Null

Write-Host ("Registered '{0}' daily at {1}" -f $TaskName, $time.ToString("HH:mm"))
Write-Host ""
Write-Host "Test it now with:"
Write-Host "  Start-ScheduledTask -TaskPath '$TaskPath' -TaskName '$TaskName'"
Write-Host "Logs: $RepoRoot\data\logs\project-report-*.log"
