
import re
import pandas as pd
from pathlib import Path

LOG_DIR     = Path(r"D:/Edge_AI/Tailscale/logs")
DECODED_DIR = Path(r"D:/Edge_AI/Tailscale/decoded")
DECODED_DIR.mkdir(exist_ok=True)

def parse_frame(can_id, data):
    r = {}
    if can_id == ####:
        r["speed_hz"]         = int.from_bytes(data[0:2], "little", signed=True) / 10.0
        r["motor_ready"]      = (data[2] >> 0) & 1
        r["ac_current_raw"]   = data[7]
    elif can_id == ####:
        r["motor_temp_C"]     = data[2] - 40
        r["inverter_temp_C"]  = int.from_bytes([data[3]], signed=True)
        r["soc_pct"]          = data[4]
        r["battery_voltage_V"]= int.from_bytes(data[6:8], "little") / 1000.0
    elif can_id == ####:
        r["alarm_code"]       = int.from_bytes(data[0:2], "little")
        r["odometer"]         = int.from_bytes(data[2:4], "little", signed=True)
    elif can_id == ####:
        r["target_speed_hz"]  = int.from_bytes(data[0:2], "little") / 10.0
        r["forward"]          = (data[2] >> 3) & 1
        r["reverse"]          = (data[2] >> 4) & 1
    elif can_id == ####:
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
    out = DECODED_DIR / (log_file.stem + ".csv")
    df.to_csv(out, index=False)
    print(f"Saved {len(df)} rows -> {out}")

print("Done.")  
