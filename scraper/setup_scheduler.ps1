# Run once (as Administrator) to register the twice-daily scraper task.
$bat = "C:\Projects\AudibleTool\scraper\run_scraper.bat"

$action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`""
$trigger1 = New-ScheduledTaskTrigger -Daily -At "08:00AM"
$trigger2 = New-ScheduledTaskTrigger -Daily -At "08:00PM"
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable $true `
    -WakeToRun $false

Register-ScheduledTask `
    -TaskName    "AudibleSalesScraper" `
    -Action      $action `
    -Trigger     $trigger1, $trigger2 `
    -Settings    $settings `
    -Description "Scrapes Audible sales data at 8 AM and 8 PM daily" `
    -RunLevel    Highest `
    -Force

Write-Host "Task registered. Logs will appear in: C:\Projects\AudibleTool\scraper\logs\scraper.log"
