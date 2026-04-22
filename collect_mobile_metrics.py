import subprocess
import requests
import time
import re

API_URL = "http://127.0.0.1:8000/mobile_metrics"

# -------------------------
# Get connected phones
# -------------------------

def get_devices():
    result = subprocess.run(
        "adb devices",
        shell=True,
        capture_output=True,
        text=True
    )

    devices = []
    for line in result.stdout.split("\n"):
        if "\tdevice" in line:
            devices.append(line.split("\t")[0])

    return devices

# -------------------------
# Extract Floats from output
# -------------------------
def extract_speed(text):
    match = re.search(r"([\d\.]+)", text)
    if match:
        return float(match.group(1))
    return 0.0

# -------------------------
# Mobile Read Speed
# -------------------------

def mobile_read(device):
    cmd = f"adb -s {device} shell dd if=/data/local/tmp/testfile of=/dev/null bs=4M count=50"
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    for line in r.stderr.split("\n"):
        if "copied" in line:
            return extract_speed(line.split(",")[-1].strip())

    return 0.0

# -------------------------
# Mobile Write Speed
# -------------------------

def mobile_write(device):
    cmd = f"adb -s {device} shell dumpsys diskstats"
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    for line in r.stdout.split("\n"):
        if "Recent Disk Write Speed" in line:
            return extract_speed(line.split("=")[1].strip())

    return 0.0


print("Mobile Collector Started")

while True:
    devices = get_devices()

    if not devices:
        print("No mobile devices connected")
        time.sleep(3)
        continue

    for device in devices:
        read = mobile_read(device)
        write = mobile_write(device)

        payload = {
            "device_id": device,
            "read_speed": read,
            "write_speed": write
        }
        
        try:
            response = requests.post(API_URL, json=payload)
            response.raise_for_status()
        except Exception as e:
            print("API ERROR:", e)

        print("\nMobile Device:", device)
        print("Read Speed :", read)
        print("Write Speed:", write)
        print("----------------------------")

    time.sleep(1)