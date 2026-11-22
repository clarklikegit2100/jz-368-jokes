# Remove the "JZ Projects" scheduled task(s).
$ErrorActionPreference = "Stop"
Get-ScheduledTask -TaskPath "\JZ Projects\" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false
Write-Host "Removed JZ Projects scheduled tasks."
