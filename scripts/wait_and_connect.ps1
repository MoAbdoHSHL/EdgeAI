
@'
Write-Host "Waiting for vehicle to come online..."
while ($true) {
    $result = & "C:\Program Files\Tailscale\tailscale.exe" ping ########### 2>&1
    if ($result -match "pong") {
        Write-Host "Vehicle is UP! Connecting..."
        ssh ############
        break
    }
    Write-Host "Still offline, retrying in 15s..."
    Start-Sleep 15
}
'@ | Out-File -FilePath "D:\Edge_AI\Tailscale\scripts\wait_and_connect.ps1" -Encoding UTF8
