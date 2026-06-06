param()
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ROOT    = "C:\Projects\AudibleTool"
$PYTHON  = "$ROOT\scraper\.venv\Scripts\python.exe"
$SCRIPT  = "$ROOT\scraper\scraper.py"
$LOGDIR  = "$ROOT\scraper\logs"

if (-not (Test-Path $LOGDIR)) { New-Item -ItemType Directory -Path $LOGDIR | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$runLog    = "$LOGDIR\run_$timestamp.log"
$latestLog = "$LOGDIR\latest.log"

# --- Tray icon ---
$tray          = New-Object System.Windows.Forms.NotifyIcon
$tray.Icon     = [System.Drawing.SystemIcons]::Information
$tray.Text     = "Audible Scraper Running..."
$tray.Visible  = $true
$tray.ShowBalloonTip(4000, "Audible Scraper", "Scrape started ($timestamp)", [System.Windows.Forms.ToolTipIcon]::Info)

# --- Run scraper, tee output to per-run log ---
"=== RUN STARTED $timestamp ===" | Out-File -FilePath $runLog -Encoding utf8
try {
    & $PYTHON -u $SCRIPT 2>&1 | Tee-Object -FilePath $runLog -Append
    $exitCode = $LASTEXITCODE
} catch {
    "ERROR: $_" | Out-File -FilePath $runLog -Append
    $exitCode = 1
}
"=== RUN ENDED $(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss') (exit $exitCode) ===" | Out-File -FilePath $runLog -Append

# Update latest.log (copy, not symlink — works without admin rights)
Copy-Item -Path $runLog -Destination $latestLog -Force

# --- Notify done ---
if ($exitCode -eq 0) {
    $msg  = "Scrape complete. Log: run_$timestamp.log"
    $icon = [System.Windows.Forms.ToolTipIcon]::Info
} else {
    $msg  = "Scrape FAILED (exit $exitCode). Check run_$timestamp.log"
    $icon = [System.Windows.Forms.ToolTipIcon]::Error
}
$tray.ShowBalloonTip(6000, "Audible Scraper", $msg, $icon)
Start-Sleep -Seconds 7   # keep balloon visible
$tray.Visible = $false
$tray.Dispose()
