
@'
$remote    = "stud@100.116.152.100"
$localLogs = "D:\Edge_AI\Tailscale\logs\"

# Create log folder on vehicle and start capturing
Write-Host "Starting CAN capture on vehicle... Press Ctrl+C when done driving."
ssh $remote "mkdir -p /home/stud/can_logs && candump -l can0 -G /home/stud/can_logs/can_`$(date +%Y%m%d_%H%M%S).log"

# Pull logs after Ctrl+C
Write-Host "Pulling logs to $localLogs ..."
scp "${remote}:/home/stud/can_logs/*.log" $localLogs
Write-Host "Done. Logs saved to $localLogs"
'@ | Out-File -FilePath "D:\Edge_AI\Tailscale\scripts\capture_and_pull.ps1" -Encoding UTF8