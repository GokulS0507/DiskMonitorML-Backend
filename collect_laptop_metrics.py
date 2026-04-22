import psutil
import requests
import time
import socket
DEVICE_ID = socket.gethostname()
API_URL = "http://127.0.0.1:8000/laptop_metrics"

prev = psutil.disk_io_counters()

while True:
    time.sleep(1)

    curr = psutil.disk_io_counters()

    read = curr.read_bytes - prev.read_bytes
    write = curr.write_bytes - prev.write_bytes

    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent

    prev = curr
    
    payload = {
        "device_id": DEVICE_ID,
        "read_bytes": read,
        "write_bytes": write,
        "cpu_usage": cpu,
        "memory_usage": mem
    }

    try:
        response = requests.post(API_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print("API ERROR:", e)

    print("Laptop:", read, write, cpu, mem)