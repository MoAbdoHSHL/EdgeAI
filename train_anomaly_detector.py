# 03_Models/train_anomaly_detector.py
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import matplotlib.pyplot as plt
import seaborn as sns

# Load data
X_train = np.load('X_train.npy')
X_test = np.load('X_test.npy')
y_train = np.load('y_train.npy')
y_test = np.load('y_test.npy')

print(f"Training samples: {len(X_train)}")
print(f"Test samples: {len(X_test)}")

# Train model
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    random_state=42,
    class_weight='balanced'
)

model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("\n" + "="*50)
print("MODEL PERFORMANCE")
print("="*50)
print(f"Accuracy: {accuracy:.4f}")
print("\nClassification Report:")
print(classification_report(y_test, y_pred))
print("\nConfusion Matrix:")
print(confusion_matrix(y_test, y_pred))

# Save model
joblib.dump(model, 'models/anomaly_detector.pkl')
print("\n✅ Model saved to models/anomaly_detector.pkl")

# Feature importance
feature_names = []
with open('feature_names.txt', 'r') as f:
    feature_names = f.read().split('\n')

importances = model.feature_importances_
indices = np.argsort(importances)[::-1]

print("\nFeature Importance:")
for i in range(len(feature_names)):
    print(f"  {i+1}. {feature_names[indices[i]]}: {importances[indices[i]]:.4f}")

# Plot confusion matrix
plt.figure(figsize=(8, 6))
cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
plt.title('Confusion Matrix - Anomaly Detection')
plt.ylabel('True Label')
plt.xlabel('Predicted Label')
plt.savefig('models/confusion_matrix.png', dpi=150)
plt.show()

print("✅ Confusion matrix saved")