import joblib
import requests
import pandas as pd
import os

# Load saved model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "../models/disk_io_model.pkl")
try:
    model = joblib.load(MODEL_PATH)
    print("Model loaded")
except Exception as e:
    print(f"Error loading model: {e}")
    exit()

# Fetch latest data from Backend API
# We'll use a specific device_id or just get the latest from all
API_URL = "http://127.0.0.1:8000/laptop_history?limit=1"

try:
    response = requests.get(API_URL)
    response.raise_for_status()
    data = response.json()
    
    if not data:
        print("No data found to predict. Run collector first.")
        exit()
        
    df = pd.DataFrame(data)
except Exception as e:
    print(f"API Error: {e}")
    exit()

# Predict using the same features as training
# Features: write_bytes, cpu_usage, memory_usage
X = df[["write_bytes", "cpu_usage", "memory_usage"]]
prediction = model.predict(X)

print("\nPredicted Future Disk Read Bytes:", int(prediction[0]))

# Interpret prediction into system status
GB = 1024 * 1024 * 1024
predicted_gb = prediction[0] / GB

if predicted_gb < 0.5:
    status = "NORMAL"
elif predicted_gb < 1:
    status = "WARNING"
else:
    status = "CRITICAL"

print(f"Predicted Disk Read Load: {predicted_gb:.2f} GB")
print(f"System Status: {status}")

