# 02_Training_Data/prepare_training_data.py
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
import os

# Load time series data
with open('D:/NoBackup/svn/Tasks_Code/Edge_AI/decoded_can_messages.json', 'r') as f:
    data = json.load(f)

print(f"Loaded {len(data)} records")

# Create sliding window features
window_size = 10
features = []
labels = []
timestamps = []

for i in range(len(data) - window_size - 1):
    window = data[i:i+window_size]
    next_msg = data[i+window_size]
    
    # Extract features from window
    feature_vector = []
    
    # Speed statistics
    speeds = [w.get('speed_hz', 0) for w in window]
    feature_vector.extend([
        np.mean(speeds),
        np.std(speeds),
        max(speeds),
        min(speeds),
        speeds[-1]  # latest speed
    ])
    
    # Toggle bit pattern
    toggles = [w.get('toggle_bit', 0) for w in window]
    feature_vector.extend([
        np.mean(toggles),
        sum(1 for i in range(1, len(toggles)) if toggles[i] != toggles[i-1])  # toggle changes
    ])
    
    # Brake and power
    brakes = [w.get('brake', 0) for w in window]
    power = [w.get('power_enabled', 0) for w in window]
    feature_vector.extend([
        np.mean(brakes),
        np.mean(power)
    ])
    
    # Time deltas
    times = [w.get('timestamp', 0) for w in window]
    if len(times) > 1:
        time_deltas = [times[j] - times[j-1] for j in range(1, len(times))]
        feature_vector.extend([
            np.mean(time_deltas),
            np.std(time_deltas)
        ])
    else:
        feature_vector.extend([0, 0])
    
    # Label: Is there an anomaly? (toggle bit stuck)
    current_toggle = window[-1].get('toggle_bit', 0)
    next_toggle = next_msg.get('toggle_bit', 0)
    label = 1 if current_toggle == next_toggle else 0
    
    features.append(feature_vector)
    labels.append(label)
    timestamps.append(next_msg.get('timestamp', 0))

# Convert to numpy arrays
X = np.array(features)
y = np.array(labels)

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Save
np.save('X_train.npy', X_train)
np.save('X_test.npy', X_test)
np.save('y_train.npy', y_train)
np.save('y_test.npy', y_test)

# Save feature names
feature_names = [
    'speed_mean', 'speed_std', 'speed_max', 'speed_min', 'speed_latest',
    'toggle_mean', 'toggle_changes', 'brake_mean', 'power_mean',
    'time_delta_mean', 'time_delta_std'
]

with open('feature_names.txt', 'w') as f:
    f.write('\n'.join(feature_names))

print(f"✅ Training data saved")
print(f"   X_train: {X_train.shape}")
print(f"   X_test: {X_test.shape}")
print(f"   Anomaly ratio: {y.sum()}/{len(y)} = {y.sum()/len(y)*100:.2f}%")