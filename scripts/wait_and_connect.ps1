
@'
Write-Host "Waiting for vehicle to come online..."
while ($true) {
    $result = & "C:\Program Files\Tailscale\tailscale.exe" ping 100.116.152.100 2>&1
    if ($result -match "pong") {
        Write-Host "Vehicle is UP! Connecting..."
        ssh stud@100.116.152.100
        break
    }
    Write-Host "Still offline, retrying in 15s..."
    Start-Sleep 15
}
'@ | Out-File -FilePath "D:\Edge_AI\Tailscale\scripts\wait_and_connect.ps1" -Encoding UTF8