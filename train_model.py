import requests
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import joblib

# Fetch data from Backend API (Firebase)
API_URL = "http://127.0.0.1:8000/laptop_history?limit=1000"

try:
    response = requests.get(API_URL)
    response.raise_for_status()
    data = response.json()
    
    if not data:
        print("No data found in database. Run the collector first.")
        exit()
        
    df = pd.DataFrame(data)
except Exception as e:
    print(f"Failed to fetch data from API: {e}")
    exit()

# Features (X) and Target (y)
# Ensure columns exist
required_cols = ["write_bytes", "cpu_usage", "memory_usage", "read_bytes"]
for col in required_cols:
    if col not in df.columns:
        print(f"Missing required column in data: {col}")
        exit()

X = df[["write_bytes", "cpu_usage", "memory_usage"]]
y = df["read_bytes"]

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train model
model = LinearRegression()
model.fit(X_train, y_train)

# Save model
import os
MODEL_PATH = os.path.join(os.path.dirname(__file__), "../models/disk_io_model.pkl")
joblib.dump(model, MODEL_PATH)

print("Model retrained successfully using Firebase data")
