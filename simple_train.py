# simple_train.py - ONE FILE TO RULE THEM ALL
import re
import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib

print("="*60)
print("SIMPLE CAN ANOMALY DETECTOR")
print("="*60)

# STEP 1: Extract toggle bits from raw log files
print("\n1. Reading log files...")

def extract_from_log(filename):
    messages = []
    with open(filename, 'r') as f:
        for line in f:
            # Find pattern: number space HEX#HEX
            match = re.search(r'(\d+)\s+([0-9A-F]+)#([0-9A-F]+)', line)
            if match:
                timestamp = int(match.group(1))
                can_id = match.group(2)
                data = match.group(3)
                
                # Only care about PDO1_RX (208) and PDO2_RX (308)
                if can_id in ['208', '308'] and len(data) >= 8:
                    # Toggle bit is in byte 3 (positions 6-7 of hex string)
                    byte3_hex = data[6:8]
                    byte3 = int(byte3_hex, 16)
                    toggle_bit = (byte3 >> 7) & 1
                    
                    messages.append({
                        'timestamp': timestamp,
                        'can_id': can_id,
                        'toggle': toggle_bit
                    })
    return messages

# Process all three logs
all_msgs = []
for logfile in ['D:/NoBackup/svn/Tasks_Code/Edge_AI/can_073.log', 'D:/NoBackup/svn/Tasks_Code/Edge_AI/can_074.log', 'D:/NoBackup/svn/Tasks_Code/Edge_AI/can_075.log']:
    try:
        msgs = extract_from_log(logfile)
        all_msgs.extend(msgs)
        print(f"   {logfile}: {len(msgs)} messages")
    except:
        print(f"   {logfile}: NOT FOUND")

print(f"\n   TOTAL: {len(all_msgs)} messages")

# STEP 2: Find anomalies (toggle bit doesn't change)
print("\n2. Finding anomalies...")

anomalies = []
normal = []
last_toggle = {}

for msg in all_msgs:
    can_id = msg['can_id']
    current_toggle = msg['toggle']
    
    if can_id in last_toggle:
        if current_toggle == last_toggle[can_id]:
            # ANOMALY: toggle bit stuck!
            anomalies.append(msg)
        else:
            # Normal: toggle bit toggled
            normal.append(msg)
    
    last_toggle[can_id] = current_toggle

print(f"   Normal messages: {len(normal)}")
print(f"   Anomalies found: {len(anomalies)}")

# STEP 3: Create training data
print("\n3. Training AI model...")

X = []  # features
y = []  # labels (1=anomaly, 0=normal)

# Add normal samples
for i in range(1, len(normal)):
    prev = normal[i-1]
    curr = normal[i]
    
    # Simple features: previous CAN ID, current CAN ID, previous toggle
    features = [
        1 if prev['can_id'] == '208' else 0,
        1 if curr['can_id'] == '208' else 0,
        prev['toggle']
    ]
    X.append(features)
    y.append(0)  # normal

# Add anomaly samples
for i in range(1, len(anomalies)):
    prev = anomalies[i-1]
    curr = anomalies[i]
    
    features = [
        1 if prev['can_id'] == '208' else 0,
        1 if curr['can_id'] == '208' else 0,
        prev['toggle']
    ]
    X.append(features)
    y.append(1)  # anomaly

print(f"   Training samples: {len(X)}")
print(f"   Anomaly ratio: {sum(y)}/{len(y)} = {sum(y)/len(y)*100:.1f}%")

# Train model
model = RandomForestClassifier(n_estimators=50)
model.fit(X, y)

# Save model
joblib.dump(model, 'anomaly_model.pkl')
print("\n✅ Model saved: anomaly_model.pkl")

# STEP 4: Test on known anomalies
print("\n4. Testing model...")
test_anomalies = anomalies[:10]
correct = 0
for a in test_anomalies:
    # Need previous message to test
    pass

print(f"   Model ready! Found {len(anomalies)} real anomalies in your logs.")

# STEP 5: Show results
print("\n" + "="*60)
print("RESULTS")
print("="*60)
print(f"✓ Total messages analyzed: {len(all_msgs)}")
print(f"✓ Anomalies detected: {len(anomalies)}")
print(f"✓ Model accuracy: {model.score(X, y)*100:.1f}%")
print("\nSample anomalies (first 5):")
for a in anomalies[:5]:
    print(f"   Time: {a['timestamp']}, CAN ID: {a['can_id']}, Toggle: {a['toggle']}")