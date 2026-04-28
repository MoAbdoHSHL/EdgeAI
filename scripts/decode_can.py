
import re
import pandas as pd
from pathlib import Path

LOG_DIR     = Path(r"D:\Edge_AI\Tailscale\logs")
DECODED_DIR = Path(r"D:\Edge_AI\Tailscale\decoded")
DECODED_DIR.mkdir(exist_ok=True)

def parse_frame(can_id, data):
    r = {}
    if can_id == 0x188:
        r["actual_speed_hz"]     = int.from_bytes(data[0:2], "little", signed=True) / 10.0
        r["nmc_status"]          = (data[2] >> 0) & 1
        r["neb_status"]          = (data[2] >> 1) & 1
        r["ac_current_raw"]      = data[7]
    elif can_id == 0x288:
        r["warning_code"]        = int.from_bytes(data[0:2], "little")
        r["motor_temp_C"]        = data[2] - 40
        r["inverter_temp_C"]     = int.from_bytes([data[3]], signed=True)
        r["soc_pct"]             = data[4]
        r["battery_current_A"]   = int.from_bytes([data[5]], signed=True)
        bat_raw                  = int.from_bytes(data[6:8], "little")
        r["battery_voltage_V"]   = round(bat_raw * 0.048, 2)
    elif can_id == 0x388:
        r["alarm_code"]          = int.from_bytes(data[0:2], "little")
        r["odometer"]            = int.from_bytes(data[2:4], "little", signed=True)
        r["steer_angle"]         = int.from_bytes(data[4:6], "little", signed=True)
        r["truck_ready"]         = (data[6] >> 0) & 1
    elif can_id == 0x208:
        r["target_speed_hz"]     = int.from_bytes(data[0:2], "little") / 10.0
        r["enable_power"]        = (data[2] >> 0) & 1
        r["forward"]             = (data[2] >> 3) & 1
        r["reverse"]             = (data[2] >> 4) & 1
    elif can_id == 0x308:
        r["max_torque_motoring"] = data[0]
        r["max_torque_braking"]  = data[1]
    return r

pattern = re.compile(r"^\((\d+\.\d+)\)\s+\w+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]+)")

for log_file in LOG_DIR.glob("*.log"):
    print(f"Decoding {log_file.name}...")
    records = []
    with open(log_file) as f:
        for line in f:
            m = pattern.match(line.strip())
            if not m:
                continue
            ts     = float(m.group(1))
            can_id = int(m.group(2), 16)
            data   = bytes.fromhex(m.group(3))
            parsed = parse_frame(can_id, data)
            if parsed:
                parsed["timestamp"] = ts
                records.append(parsed)

    df = pd.DataFrame(records).sort_values("timestamp")
    df = df.ffill().dropna(subset=["actual_speed_hz", "motor_temp_C"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")

    out = DECODED_DIR / (log_file.stem + ".csv")
    df.to_csv(out, index=False)
    
    print(f"Saved {len(df)} rows -> {out}")
    print(f"Columns: {list(df.columns)}")
    print(df.head(5).to_string())
