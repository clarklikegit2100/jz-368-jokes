# Remove the three "JZ Jokes" scheduled tasks.
$ErrorActionPreference = "Stop"
Get-ScheduledTask -TaskPath "\JZ Jokes\" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false
Write-Host "Removed JZ Jokes scheduled tasks."
