# complete_trust.py - Analyzes ALL CAN messages
import re
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from collections import defaultdict

print("="*60)
print("COMPLETE CAN TRUST MONITOR")
print("="*60)

# ============================================================
# STEP 1: Parse ALL messages from logs
# ============================================================
print("\n📂 Reading all messages from logs...")

def parse_all_messages(line):
    """Parse ALL CAN messages from log line"""
    match = re.search(r'(\d+)\s+([0-9A-F]+)#([0-9A-F]+)', line)
    if not match:
        return None
    
    timestamp = int(match.group(1))
    can_id = match.group(2)
    data = match.group(3)
    
    # Convert CAN ID to standard format (3 digits)
    can_id_hex = can_id.zfill(3)
    
    return {
        'timestamp': timestamp,
        'can_id': can_id_hex,
        'data': data,
        'data_bytes': [int(data[i:i+2], 16) for i in range(0, len(data), 2)]
    }

# Process all logs
all_messages = []
for log_file in ['D:/NoBackup/svn/Tasks_Code/Edge_AI/can_073.log', 'D:/NoBackup/svn/Tasks_Code/Edge_AI/can_074.log', 'D:/NoBackup/svn/Tasks_Code/Edge_AI/can_075.log']:
    try:
        count = 0
        with open(log_file, 'r') as f:
            for line in f:
                msg = parse_all_messages(line)
                if msg:
                    all_messages.append(msg)
                    count += 1
        print(f"   {log_file}: {count} messages")
    except FileNotFoundError:
        print(f"   {log_file}: NOT FOUND")

print(f"\n   TOTAL: {len(all_messages)} messages")

# ============================================================
# STEP 2: Extract toggle bits from 208 and 308 (Master commands)
# ============================================================
print("\n🔍 Analyzing Master commands (208, 308)...")

def extract_toggle_bit(msg):
    """Extract toggle bit based on Excel spec"""
    can_id = msg['can_id']
    data_bytes = msg['data_bytes']
    
    if can_id == '208' and len(data_bytes) >= 3:
        # PDO1_RX: toggle bit at byte 2, bit 7
        return (data_bytes[2] >> 7) & 1
    elif can_id == '308' and len(data_bytes) >= 4:
        # PDO2_RX: toggle bit at byte 3, bit 7
        return (data_bytes[3] >> 7) & 1
    return None

# Track toggle bit anomalies
master_msgs = []
last_toggle = {}
anomalies = []

for msg in all_messages:
    if msg['can_id'] in ['208', '308']:
        toggle = extract_toggle_bit(msg)
        if toggle is not None:
            master_msgs.append(msg)
            can_id = msg['can_id']
            
            if can_id in last_toggle:
                if toggle == last_toggle[can_id]:
                    # ANOMALY: toggle bit stuck
                    anomalies.append({
                        'type': 'toggle_bit_stuck',
                        'can_id': can_id,
                        'timestamp': msg['timestamp'],
                        'toggle': toggle
                    })
            last_toggle[can_id] = toggle

print(f"   Master messages: {len(master_msgs)}")
print(f"   Toggle bit anomalies: {len(anomalies)}")

# ============================================================
# STEP 3: Check Speed Command vs Feedback (208 vs 188)
# ============================================================
print("\n🔍 Analyzing Speed Command vs Feedback...")

def extract_speed(msg):
    """Extract speed from PDO1_RX (208) or PDO1_TX (188)"""
    can_id = msg['can_id']
    data_bytes = msg['data_bytes']
    
    if can_id == '208' and len(data_bytes) >= 2:
        # Commanded speed: bytes 0-1 (little endian)
        speed_raw = data_bytes[0] | (data_bytes[1] << 8)
        return speed_raw / 10  # Convert Hz/10 to Hz
    elif can_id == '188' and len(data_bytes) >= 2:
        # Actual speed feedback: bytes 0-1 (little endian)
        speed_raw = data_bytes[0] | (data_bytes[1] << 8)
        # Handle signed value (can be negative for reverse)
        if speed_raw > 32767:
            speed_raw = speed_raw - 65536
        return speed_raw / 10
    return None

# Find speed mismatches
speed_commands = {}  # timestamp -> speed
speed_feedbacks = {}  # timestamp -> speed

for msg in all_messages:
    speed = extract_speed(msg)
    if speed is not None:
        if msg['can_id'] == '208':
            speed_commands[msg['timestamp']] = speed
        elif msg['can_id'] == '188':
            speed_feedbacks[msg['timestamp']] = speed

# Check if feedback matches command (within 5 Hz tolerance)
speed_mismatches = []
for ts_cmd, cmd_speed in speed_commands.items():
    # Find closest feedback after command
    closest_fb = None
    for ts_fb, fb_speed in speed_feedbacks.items():
        if ts_fb > ts_cmd:
            closest_fb = (ts_fb, fb_speed)
            break
    
    if closest_fb:
        ts_fb, fb_speed = closest_fb
        if abs(cmd_speed - fb_speed) > 5:  # More than 5 Hz difference
            speed_mismatches.append({
                'type': 'speed_mismatch',
                'timestamp_cmd': ts_cmd,
                'timestamp_fb': ts_fb,
                'cmd_speed': cmd_speed,
                'fb_speed': fb_speed
            })

print(f"   Speed commands: {len(speed_commands)}")
print(f"   Speed feedbacks: {len(speed_feedbacks)}")
print(f"   Speed mismatches: {len(speed_mismatches)}")

# ============================================================
# STEP 4: Check Heartbeat (708) - Is inverter alive?
# ============================================================
print("\n🔍 Analyzing Heartbeat (708)...")

heartbeats = [msg for msg in all_messages if msg['can_id'] == '708']
if heartbeats:
    # Extract NMT status (byte 0)
    nmt_statuses = []
    for hb in heartbeats[:20]:  # Check first 20
        if hb['data_bytes']:
            status = hb['data_bytes'][0]
            status_names = {0: 'Initializing', 127: 'Stopped', 5: 'Operational', 127: 'Pre-operational'}
            nmt_statuses.append(status_names.get(status, f'Unknown({status})'))
    
    print(f"   Heartbeat messages: {len(heartbeats)}")
    print(f"   NMT statuses seen: {set(nmt_statuses)}")
    
    # Check if inverter ever reached Operational state
    operational = any(s == 'Operational' for s in nmt_statuses)
    print(f"   Inverter Operational: {'✅ YES' if operational else '⚠️ NO'}")
else:
    print("   No heartbeat messages found!")

# ============================================================
# STEP 5: Check Emergency messages (088)
# ============================================================
print("\n🔍 Analyzing Emergency messages (088)...")

emergencies = [msg for msg in all_messages if msg['can_id'] == '088']
if emergencies:
    print(f"   ⚠️ Emergency messages found: {len(emergencies)}")
    for em in emergencies[:5]:
        if len(em['data_bytes']) >= 4:
            alarm_code = em['data_bytes'][0] | (em['data_bytes'][1] << 8)
            print(f"      Time: {em['timestamp']}, Alarm code: {alarm_code}")
else:
    print("   No emergency messages - good!")

# ============================================================
# STEP 6: Build Trust Score
# ============================================================
print("\n" + "="*60)
print("TRUST SCORE REPORT")
print("="*60)

# Calculate trust score (0-1, higher is better)
trust_score = 1.0
trust_issues = []

# Deduct for anomalies
if anomalies:
    trust_score -= len(anomalies) * 0.01
    trust_issues.append(f"{len(anomalies)} toggle bit anomalies")

# Deduct for speed mismatches
if speed_mismatches:
    trust_score -= len(speed_mismatches) * 0.02
    trust_issues.append(f"{len(speed_mismatches)} speed mismatches")

# Deduct if no operational state
if heartbeats and 'Operational' not in str(nmt_statuses):
    trust_score -= 0.2
    trust_issues.append("Inverter never reached Operational state")

# Deduct for emergencies
if emergencies:
    trust_score -= 0.3
    trust_issues.append(f"{len(emergencies)} emergency messages")

trust_score = max(0, min(1, trust_score))

print(f"\n📊 OVERALL TRUST SCORE: {trust_score:.2f}")
print(f"   {'✅ TRUSTED' if trust_score > 0.7 else '⚠️ DEGRADED' if trust_score > 0.3 else '🔴 UNTRUSTWORTHY'}")

if trust_issues:
    print(f"\n📋 Trust issues found:")
    for issue in trust_issues:
        print(f"   - {issue}")

# ============================================================
# STEP 7: Train combined anomaly detection model
# ============================================================
print("\n🤖 Training combined anomaly detection model...")

# Create features from all messages
X = []
y = []

for i in range(1, len(all_messages)):
    prev = all_messages[i-1]
    curr = all_messages[i]
    
    # Features: previous CAN ID, current CAN ID, time delta
    features = [
        int(prev['can_id'], 16),
        int(curr['can_id'], 16),
        curr['timestamp'] - prev['timestamp']
    ]
    
    # Label: 1 if this is part of an anomaly pattern
    # Simple rule: same CAN ID repeating too fast
    label = 1 if prev['can_id'] == curr['can_id'] and (curr['timestamp'] - prev['timestamp']) < 10000 else 0
    
    X.append(features)
    y.append(label)

if len(X) > 0:
    model = RandomForestClassifier(n_estimators=50)
    model.fit(X, y)
    joblib.dump(model, 'complete_trust_model.pkl')
    print(f"   Model trained on {len(X)} samples")
    print(f"   Anomaly patterns found: {sum(y)}")
    print(f"   Model saved: complete_trust_model.pkl")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "="*60)
print("FINAL SUMMARY")
print("="*60)
print(f"✅ Total messages analyzed: {len(all_messages)}")
print(f"✅ Master commands (208,308): {len(master_msgs)}")
print(f"✅ Heartbeat messages: {len(heartbeats)}")
print(f"⚠️  Toggle bit anomalies: {len(anomalies)}")
print(f"⚠️  Speed mismatches: {len(speed_mismatches)}")
print(f"⚠️  Emergency messages: {len(emergencies)}")
print(f"\n🎯 Trust Score: {trust_score:.2f}")
print("="*60)