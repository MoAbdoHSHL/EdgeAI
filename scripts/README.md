# wait_and_connect.ps1
Pings the vehicle every 15 seconds over Tailscale until it comes online.
Automatically opens an SSH connection the moment it responds.
Run this first and leave it waiting in the background.

# capture_and_pull.ps1
SSHes into the vehicle and starts recording all CAN bus messages.
Press Ctrl+C when the drive is done — it will pull the log file to D:\Edge_AI\Tailscale\logs\
Run this in a new PowerShell window once SSH is connected.

# decode_can.py
Reads every .log file in the logs folder and decodes the raw CAN frames.
Translates bytes into human-readable values: speed, temperature, battery, alarms.
Saves a clean CSV file per log into D:\Edge_AI\Tailscale\decoded\

# Notes & Commands:
powershell -ExecutionPolicy Bypass -File "D:\Edge_AI\Tailscale\scripts\wait_and_connect.ps1"

keep it runnin on a seperate window

powershell -ExecutionPolicy Bypass -File "D:\Edge_AI\Tailscale\scripts\capture_and_pull.ps1"

When done, press Ctrl+C

python "D:\Edge_AI\Tailscale\scripts\decode_can.py"
