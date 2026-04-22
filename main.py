from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, db as rtdb
import mysql.connector
from mysql.connector import pooling
import datetime
import os
import glob
import re

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# MySQL Configuration
# -------------------------
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "12344321@Gg",
    "database": "disk_io_db"
}

db_pool = None
try:
    # First connect without database to ensure it exists
    conn = mysql.connector.connect(
        host=MYSQL_CONFIG["host"],
        user=MYSQL_CONFIG["user"],
        password=MYSQL_CONFIG["password"]
    )
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_CONFIG['database']}")
    cursor.close()
    conn.close()

    db_pool = pooling.MySQLConnectionPool(
        pool_name="disk_pool",
        pool_size=5,
        **MYSQL_CONFIG
    )
    # Ensure separate tables exist
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    
    # Laptop Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS laptop_metrics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(255),
            read_bytes BIGINT DEFAULT 0,
            write_bytes BIGINT DEFAULT 0,
            cpu_usage FLOAT DEFAULT 0,
            memory_usage FLOAT DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Mobile Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mobile_metrics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(255),
            read_speed FLOAT DEFAULT 0,
            write_speed FLOAT DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("MySQL initialized with separate tables successfully.")
except Exception as e:
    print(f"Error initializing MySQL: {e}")

# -------------------------
# Firebase (Keeping for compatibility)
# -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
json_files = glob.glob(os.path.join(BASE_DIR, "*firebase-adminsdk*.json"))
cred_path = json_files[0] if json_files else os.path.join(BASE_DIR, "serviceAccountKey.json")

db_instance = None
if os.path.exists(cred_path):
    try:
        cred = credentials.Certificate(cred_path)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://disk-io-performance-default-rtdb.asia-southeast1.firebasedatabase.app'
            })
        db_instance = True
        print("Firebase RTDB initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        db_instance = None

def sanitize_key(key: str) -> str:
    return re.sub(r'[\.\$\#\[\]\/]', '_', key)

class LaptopMetricIn(BaseModel):
    device_id: str
    read_bytes: int
    write_bytes: int
    cpu_usage: float
    memory_usage: float

class MobileMetricIn(BaseModel):
    device_id: str
    read_speed: float
    write_speed: float

# -------------------------
# Laptop Operations
# -------------------------

@app.get("/laptop_devices")
def laptop_devices():
    devices = []
    if db_pool:
        try:
            conn = db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT device_id FROM laptop_metrics")
            devices = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
        except Exception as e:
            print("MySQL fetch laptop devices error:", e)

    if not devices and db_instance:
        try:
            devices_dict = rtdb.reference("laptop_latest").get()
            if devices_dict: devices = list(devices_dict.keys())
        except: pass
    
    if not devices: devices = ["mock-laptop-1"]
    return {"devices": devices}

@app.get("/laptop_metrics")
def laptop_metrics(device_id: str):
    data = None
    if db_pool:
        try:
            conn = db_pool.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM laptop_metrics WHERE device_id=%s ORDER BY timestamp DESC LIMIT 1", (device_id,))
            data = cursor.fetchone()
            cursor.close()
            conn.close()
        except Exception as e:
            print("MySQL fetch laptop metric error:", e)

    if not data and db_instance:
        try:
            data = rtdb.reference(f"laptop_latest/{device_id}").get()
        except: pass

    if not data:
        return {
            "read_bytes": 1024500, "write_bytes": 512200, 
            "cpu_usage": 45.2, "memory_usage": 60.1, 
            "predicted_disk_load_mb": 1.54, "status": "NORMAL"
        }
    
    rb = data.get("read_bytes", 0)
    wb = data.get("write_bytes", 0)
    predicted = round((rb + wb) / 1000000, 2)
    status = "NORMAL"
    if predicted >= 5: status = "CRITICAL"
    elif predicted >= 1: status = "WARNING"

    return {
        "read_bytes": rb,
        "write_bytes": wb,
        "cpu_usage": data.get("cpu_usage", 0.0),
        "memory_usage": data.get("memory_usage", 0.0),
        "predicted_disk_load_mb": predicted,
        "status": status
    }

@app.post("/laptop_metrics")
def save_laptop_metrics(metric: LaptopMetricIn):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    if db_pool:
        try:
            conn = db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO laptop_metrics (device_id, read_bytes, write_bytes, cpu_usage, memory_usage)
                VALUES (%s, %s, %s, %s, %s)
            """, (metric.device_id, metric.read_bytes, metric.write_bytes, metric.cpu_usage, metric.memory_usage))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"DEBUG: Saved Laptop Data for {metric.device_id}")
        except Exception as e:
            print("MySQL Laptop Save Error:", e)

    if db_instance:
        try:
            data = metric.dict()
            data["timestamp"] = timestamp
            safe_id = sanitize_key(metric.device_id)
            rtdb.reference(f"laptop_latest/{safe_id}").set(data)
            rtdb.reference("laptop_history").push(data)
        except: pass
            
    return {"message": "Data saved successfully"}

@app.get("/laptop_history")
def laptop_history(limit: int = 100):
    if db_pool:
        try:
            conn = db_pool.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM laptop_metrics ORDER BY timestamp DESC LIMIT %s", (limit,))
            history = cursor.fetchall()
            cursor.close()
            conn.close()
            return history
        except Exception as e:
            print("MySQL laptop history error:", e)

    if db_instance:
        try:
            data = rtdb.reference("laptop_history").order_by_key().limit_to_last(limit).get()
            return list(data.values()) if data else []
        except: pass
    
    return []

# -------------------------
# Mobile Operations
# -------------------------

@app.get("/mobile_devices")
def mobile_devices():
    devices = []
    if db_pool:
        try:
            conn = db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT device_id FROM mobile_metrics")
            devices = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
        except: pass

    if not devices and db_instance:
        try:
            devices_dict = rtdb.reference("mobile_latest").get()
            if devices_dict: devices = list(devices_dict.keys())
        except: pass
        
    if not devices: devices = ["mock-mobile-1"]
    return {"devices": devices}

@app.get("/mobile_metrics")
def mobile_metrics(device_id: str):
    data = None
    if db_pool:
        try:
            conn = db_pool.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM mobile_metrics WHERE device_id=%s ORDER BY timestamp DESC LIMIT 1", (device_id,))
            data = cursor.fetchone()
            cursor.close()
            conn.close()
        except: pass

    if not data and db_instance:
        try:
            data = rtdb.reference(f"mobile_latest/{device_id}").get()
        except: pass

    if not data:
        return {"mobile_read_speed": 45.5, "mobile_write_speed": 12.3}
        
    return {
        "mobile_read_speed": data.get("read_speed", 0.0),
        "mobile_write_speed": data.get("write_speed", 0.0)
    }

@app.post("/mobile_metrics")
def save_mobile_metrics(metric: MobileMetricIn):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if db_pool:
        try:
            conn = db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO mobile_metrics (device_id, read_speed, write_speed)
                VALUES (%s, %s, %s)
            """, (metric.device_id, metric.read_speed, metric.write_speed))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"DEBUG: Saved Mobile Data for {metric.device_id}")
        except Exception as e:
            print("MySQL Mobile Save Error:", e)

    if db_instance:
        try:
            data = metric.dict()
            data["timestamp"] = timestamp
            safe_id = sanitize_key(metric.device_id)
            rtdb.reference(f"mobile_latest/{safe_id}").set(data)
            rtdb.reference("mobile_history").push(data)
        except: pass
        
    return {"message": "Data saved successfully"}

@app.get("/mobile_history")
def mobile_history(limit: int = 100):
    if db_pool:
        try:
            conn = db_pool.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM mobile_metrics ORDER BY timestamp DESC LIMIT %s", (limit,))
            res = cursor.fetchall()
            cursor.close()
            conn.close()
            return res
        except: pass
    return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
from mysql.connector import pooling
import datetime
import os

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# MySQL Configuration (Railway)
# -------------------------
MYSQL_CONFIG = {
    "host": os.getenv("MYSQLHOST"),
    "user": os.getenv("MYSQLUSER"),
    "password": os.getenv("MYSQLPASSWORD"),
    "database": os.getenv("MYSQLDATABASE"),
    "port": int(os.getenv("MYSQLPORT", 3306))
}

# Debug (IMPORTANT)
print("DB HOST:", MYSQL_CONFIG["host"])
print("DB USER:", MYSQL_CONFIG["user"])
print("DB NAME:", MYSQL_CONFIG["database"])

if not MYSQL_CONFIG["host"]:
    raise Exception("❌ MYSQLHOST not set in environment variables")

# -------------------------
# Database Connection Pool
# -------------------------
db_pool = None

try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="disk_pool",
        pool_size=5,
        **MYSQL_CONFIG
    )

    conn = db_pool.get_connection()
    cursor = conn.cursor()

    # Laptop Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS laptop_metrics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(255),
            read_bytes BIGINT DEFAULT 0,
            write_bytes BIGINT DEFAULT 0,
            cpu_usage FLOAT DEFAULT 0,
            memory_usage FLOAT DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Mobile Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mobile_metrics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(255),
            read_speed FLOAT DEFAULT 0,
            write_speed FLOAT DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("✅ MySQL Connected Successfully!")

except Exception as e:
    print("❌ MySQL Connection Error:", e)


# -------------------------
# Models
# -------------------------
class LaptopMetricIn(BaseModel):
    device_id: str
    read_bytes: int
    write_bytes: int
    cpu_usage: float
    memory_usage: float


class MobileMetricIn(BaseModel):
    device_id: str
    read_speed: float
    write_speed: float


# -------------------------
# Laptop APIs
# -------------------------

@app.post("/laptop_metrics")
def save_laptop_metrics(metric: LaptopMetricIn):
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO laptop_metrics (device_id, read_bytes, write_bytes, cpu_usage, memory_usage)
            VALUES (%s, %s, %s, %s, %s)
        """, (metric.device_id, metric.read_bytes, metric.write_bytes, metric.cpu_usage, metric.memory_usage))

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Laptop data saved"}

    except Exception as e:
        return {"error": str(e)}


@app.get("/laptop_metrics")
def get_laptop_metrics(device_id: str):
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM laptop_metrics
            WHERE device_id=%s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))

        data = cursor.fetchone()
        cursor.close()
        conn.close()

        if not data:
            return {"message": "No data"}

        rb = data["read_bytes"]
        wb = data["write_bytes"]

        predicted = round((rb + wb) / 1000000, 2)

        status = "NORMAL"
        if predicted >= 5:
            status = "CRITICAL"
        elif predicted >= 1:
            status = "WARNING"

        return {
            "read_bytes": rb,
            "write_bytes": wb,
            "cpu_usage": data["cpu_usage"],
            "memory_usage": data["memory_usage"],
            "predicted_disk_load_mb": predicted,
            "status": status
        }

    except Exception as e:
        return {"error": str(e)}


# -------------------------
# Mobile APIs
# -------------------------

@app.post("/mobile_metrics")
def save_mobile_metrics(metric: MobileMetricIn):
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO mobile_metrics (device_id, read_speed, write_speed)
            VALUES (%s, %s, %s)
        """, (metric.device_id, metric.read_speed, metric.write_speed))

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Mobile data saved"}

    except Exception as e:
        return {"error": str(e)}


@app.get("/mobile_metrics")
def get_mobile_metrics(device_id: str):
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM mobile_metrics
            WHERE device_id=%s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))

        data = cursor.fetchone()
        cursor.close()
        conn.close()

        if not data:
            return {"message": "No data"}

        return {
            "mobile_read_speed": data["read_speed"],
            "mobile_write_speed": data["write_speed"]
        }

    except Exception as e:
        return {"error": str(e)}


# -------------------------
# Root
# -------------------------
@app.get("/")
def home():
    return {"message": "DiskMonitor ML Backend Running 🚀"}
