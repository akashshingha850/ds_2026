import json
import logging
import os
import sys
import time
from datetime import datetime

import psutil
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String

# Allow importing the shared config / helpers copied into /app
sys.path.append('.')

from config import SYSTEM_MONITOR_INTERVAL, TOPIC_SYSTEM_STATUS
from ros_common import resolve_device_hostname, ros_namespace, setup_logging


def get_memory_status():
    """Get memory usage."""
    mem = psutil.virtual_memory()
    return {
        'total': mem.total,
        'available': mem.available,
        'percent': mem.percent,
        'used': mem.used,
    }


def get_temperature_status():
    """Get system temperature (first available sensor)."""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for _sensor, readings in temps.items():
                if readings:
                    return f"{readings[0].current}°C"
        return "N/A"
    except Exception:
        return "N/A"


def get_speeds():
    """Get disk and network I/O speeds over SYSTEM_MONITOR_INTERVAL."""
    io1 = psutil.disk_io_counters()
    net1 = psutil.net_io_counters()
    time.sleep(SYSTEM_MONITOR_INTERVAL)
    io2 = psutil.disk_io_counters()
    net2 = psutil.net_io_counters()

    if io1 and io2:
        read_speed = (io2.read_bytes - io1.read_bytes) / SYSTEM_MONITOR_INTERVAL
        write_speed = (io2.write_bytes - io1.write_bytes) / SYSTEM_MONITOR_INTERVAL
    else:
        read_speed = write_speed = 0

    if net1 and net2:
        send_speed = (net2.bytes_sent - net1.bytes_sent) / SYSTEM_MONITOR_INTERVAL
        recv_speed = (net2.bytes_recv - net1.bytes_recv) / SYSTEM_MONITOR_INTERVAL
    else:
        send_speed = recv_speed = 0

    return {
        'read_speed': read_speed,
        'write_speed': write_speed,
        'send_speed': send_speed,
        'recv_speed': recv_speed,
    }


class SystemMonitor(Node):
    def __init__(self):
        super().__init__('system_monitor', namespace=ros_namespace())
        self.node_id = f"{resolve_device_hostname()}-system_monitor"

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self.status_pub = self.create_publisher(String, TOPIC_SYSTEM_STATUS, qos)
        # get_speeds() blocks for SYSTEM_MONITOR_INTERVAL, so each callback is
        # already paced by that sample window; use a 0s timer and let the
        # blocking sample set the cadence.
        self.timer = self.create_timer(0.0, self.publish_status)

        logging.info(f"[STATUS_PUB:{self.node_id}] Publishing on topic '{TOPIC_SYSTEM_STATUS}'")

    def publish_status(self):
        """Sample system metrics and publish them over ROS 2."""
        speeds = get_speeds()  # includes the interval sleep
        cpu = psutil.cpu_percent(interval=0)
        mem = get_memory_status()
        temp = get_temperature_status()
        ts = datetime.now().isoformat()

        status_data = {
            'type': 'system_status',
            'node_id': self.node_id,
            'timestamp': ts,
            'cpu': cpu,
            'memory_used_gb': mem['used'] / (1024 ** 3),
            'memory_total_gb': mem['total'] / (1024 ** 3),
            'memory_percent': mem['percent'],
            'disk_read_kbs': speeds['read_speed'] / 1024,
            'disk_write_kbs': speeds['write_speed'] / 1024,
            'network_send_kbs': speeds['send_speed'] / 1024,
            'network_recv_kbs': speeds['recv_speed'] / 1024,
            'temperature': temp,
        }

        msg = String()
        msg.data = json.dumps(status_data)
        self.status_pub.publish(msg)

        logging.info(
            f"Node ID: {self.node_id}, "
            f"CPU: {cpu}%, "
            f"Memory: {mem['used'] / (1024 ** 3):.2f}/{mem['total'] / (1024 ** 3):.2f} GB ({mem['percent']}%), "
            f"Temp: {temp}, "
            f"Disk R/W: {speeds['read_speed'] / 1024:.2f}/{speeds['write_speed'] / 1024:.2f} KB/s, "
            f"Network U/D: {speeds['send_speed'] / 1024:.2f}/{speeds['recv_speed'] / 1024:.2f} KB/s"
        )


def main():
    setup_logging()
    rclpy.init()
    monitor = SystemMonitor()
    print(f"[MONITOR:{monitor.node_id}] System monitor started\n")
    try:
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        logging.info("User stopped system monitoring with Ctrl+C.")
    finally:
        monitor.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
