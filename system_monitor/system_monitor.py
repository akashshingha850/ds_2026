
import psutil
import time
from shared.config import SYSTEM_MONITOR_INTERVAL, SYSTEM_MONITOR_PORT, DISCOVERY_PORT_SYSTEM
from datetime import datetime
import socket
import logging
import sys
import zmq
from shared.utils import ZMQNode

# Override logging settings: logs/<hostname>-top-time(HH.MM.SS).log
import os
hostname = socket.gethostname()
now = datetime.now().strftime('%H.%M.%S')
log_filename = f"logs/{hostname}-htop-{now}.log"
# Remove all handlers associated with the root logger object
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
# Add console handler again
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)


# Add parent directory to path to import config
sys.path.append('.')


def get_cpu_status():
    """Get CPU usage percentage."""
    return psutil.cpu_percent(interval=SYSTEM_MONITOR_INTERVAL)

def get_memory_status():
    """Get memory usage."""
    mem = psutil.virtual_memory()
    return {
        'total': mem.total,
        'available': mem.available,
        'percent': mem.percent,
        'used': mem.used
    }

def get_disk_status_static():
    """Get disk usage (static, no speed)."""
    disk = psutil.disk_usage('/')
    return {
        'total': disk.total,
        'used': disk.used,
        'free': disk.free,
        'percent': disk.percent
    }

def get_network_status_static(net_counters):
    """Get network I/O statistics (static, no speed)."""
    return {
        'bytes_sent': net_counters.bytes_sent,
        'bytes_recv': net_counters.bytes_recv,
        'packets_sent': net_counters.packets_sent,
        'packets_recv': net_counters.packets_recv
    }

def get_temperature_status():
    """Get system temperatures."""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            # Return the first available temperature sensor
            for sensor, readings in temps.items():
                if readings:
                    temp_value = readings[0].current
                    return f"{temp_value}°C"
        return "Temperature sensors not available"
    except Exception as e:
        return 'N/A' # f"Error getting temperature: {e}"


def get_speeds():
    """Get disk and network I/O speeds over SYSTEM_MONITOR_INTERVAL."""
    # Get initial counters for speed calculations
    io1 = psutil.disk_io_counters()
    net1 = psutil.net_io_counters()
    # Sleep for interval
    time.sleep(SYSTEM_MONITOR_INTERVAL)

    # Get final counters
    io2 = psutil.disk_io_counters()
    net2 = psutil.net_io_counters()

    # Calculate speeds
    if io1 and io2:
        read_speed = (io2.read_bytes - io1.read_bytes) / SYSTEM_MONITOR_INTERVAL
        write_speed = (io2.write_bytes - io1.write_bytes) / SYSTEM_MONITOR_INTERVAL
    else:
        read_speed = 0
        write_speed = 0
    
    if net1 and net2:
        send_speed = (net2.bytes_sent - net1.bytes_sent) / SYSTEM_MONITOR_INTERVAL
        recv_speed = (net2.bytes_recv - net1.bytes_recv) / SYSTEM_MONITOR_INTERVAL
    else:
        send_speed = 0
        recv_speed = 0

    return {
        'read_speed': read_speed,
        'write_speed': write_speed,
        'send_speed': send_speed,
        'recv_speed': recv_speed,
    }

class SystemMonitor(ZMQNode):
    def __init__(self):
        super().__init__('system_monitor', discovery_port=DISCOVERY_PORT_SYSTEM)
        self.pub_port = SYSTEM_MONITOR_PORT  # For discovery
        self.status_pub = self.context.socket(zmq.PUB)
        self.status_pub.bind(f"tcp://*:{SYSTEM_MONITOR_PORT}")

    def publish_status(self, speeds, cpu_usage, mem, temp, ts):
        """Publish system status via ZeroMQ."""
        
        status_data = {
            'type': 'system_status',
            'node_id': self.node_id,
            'timestamp': ts,
            'cpu': cpu_usage,
            'memory_used_gb': mem['used'] / (1024**3),
            'memory_total_gb': mem['total'] / (1024**3),
            'memory_percent': mem['percent'],
            'disk_read_kbs': speeds['read_speed'] / 1024,
            'disk_write_kbs': speeds['write_speed'] / 1024,
            'network_send_kbs': speeds['send_speed'] / 1024,
            'network_recv_kbs': speeds['recv_speed'] / 1024,
            'temperature': temp,
        }
        
        self.status_pub.send_json(status_data)
        
        # Also log locally
        message = (
            # f"{ts},"
            # f"Node ID: {self.node_id}, "
            f"CPU: {cpu_usage}%, "
            f"Memory: {mem['used'] / (1024**3):.2f}/{mem['total'] / (1024**3):.2f} GB ({mem['percent']}%), "
            f"Temp: {temp}, "
            f"Disk R/W: {speeds['read_speed'] / 1024:.2f}/{speeds['write_speed'] / 1024:.2f} KB/s, "
            f"Network U/D: {speeds['send_speed'] / 1024:.2f}/{speeds['recv_speed'] / 1024:.2f} KB/s, "
        )
        logging.info(message)

    def save_log(self, cpu_usage, mem, speeds, temp, ts):
        """Save system status to a local log file."""

        log_message = (
            f"{ts},"
            f"Node ID: {self.node_id}, "
            f"CPU: {cpu_usage}%, "
            f"Memory: {mem['used'] / (1024**3):.2f}/{mem['total'] / (1024**3):.2f} GB ({mem['percent']}%), "
            f"Disk R/W: {speeds['read_speed'] / 1024:.2f}/{speeds['write_speed'] / 1024:.2f} KB/s, "
            f"Network U/D: {speeds['send_speed'] / 1024:.2f}/{speeds['recv_speed'] / 1024:.2f} KB/s, "
            f"Temp: {temp}, "
        )
        logging.info(log_message)

    def run(self):
        # Start discovery thread
        self.start_discovery()

        logging.info(f"[STATUS_PUB:{self.node_id}] Listening on tcp://*:{SYSTEM_MONITOR_PORT}")
        logging.info(f"[PUB:{self.node_id}] Local IP: {self.local_ip}")

        logging.info("Starting system monitoring... Press Ctrl+C to stop.")

        try:
            while True:
                # Get speeds (includes sleep)
                speeds = get_speeds()

                # Get other stats
                cpu = psutil.cpu_percent(interval=0)
                mem = get_memory_status()
                temp = get_temperature_status()
                ts = datetime.now().isoformat()

                # self.save_log(cpu, mem, speeds, temp, ts)
                self.publish_status(speeds, cpu, mem, temp, ts)

        except KeyboardInterrupt:
            logging.info("User stopped system monitoring with Ctrl+C.")
        finally:
            self.status_pub.close()
            self.cleanup()


if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.run()
