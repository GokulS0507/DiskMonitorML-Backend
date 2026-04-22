import psutil
import time
from datetime import datetime

while True:
    disk = psutil.disk_io_counters()
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent

    print("Time:", datetime.now())
    print("Read Bytes:", disk.read_bytes)
    print("Write Bytes:", disk.write_bytes)
    print("Read Time:", disk.read_time)
    print("Write Time:", disk.write_time)
    print("CPU Usage:", cpu)
    print("Memory Usage:", memory)
    print("-" * 40)

    time.sleep(2)
