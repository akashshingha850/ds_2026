# System Monitor

## Overview

`system_monitor.py` continuously collects local system metrics and publishes them via ZeroMQ while logging to file and console.

It extends `ZMQNode` and uses hostname-aware node IDs (for example, `my-pi-system_monitor`) based on `resolve_device_hostname()`.

## Features

- **CPU Usage**: Percentage of CPU utilization.
- **Memory Usage**: Used and total memory in GB, along with usage percentage.
- **Disk I/O**: Read and write speeds in KB/s.
- **Network I/O**: Send (upload) and receive (download) speeds in KB/s.
- **CPU Temperature**: System temperature from available sensors.
- **ZeroMQ Broadcasting**: Publishes status data as JSON to subscribers.
- **Peer Discovery**: Automatic discovery of other nodes on the network via UDP broadcast.

## Architecture

The `SystemMonitor` class extends `ZMQNode` and implements:
- **Publisher Socket**: Binds to `tcp://*:{SYSTEM_MONITOR_PORT}` for broadcasting status updates.
- **Discovery Thread**: Runs in background to announce presence and discover peer nodes.
- **Structured JSON Output**: Publishes comprehensive system metrics in a structured format.

## Dependencies

- `psutil`: For system and hardware monitoring.
- `zmq` (pyzmq): For ZeroMQ messaging.
- `config.py`: Imports `SYSTEM_MONITOR_INTERVAL`, `SYSTEM_MONITOR_PORT`, `DISCOVERY_PORT_SYSTEM`.
- `utils.py`: Provides `ZMQNode` and `resolve_device_hostname`.

## Configuration

Configuration values from `config.py`:
- `SYSTEM_MONITOR_INTERVAL`: Time interval (in seconds) over which speeds are calculated and between status updates (default: 1).
- `SYSTEM_MONITOR_PORT`: ZeroMQ port for publishing status data (default: 5559).
- `DISCOVERY_PORT_SYSTEM`: UDP discovery port for system monitor nodes (default: 50001).

## Usage

### Run with Docker Compose (recommended)

From project root:

```bash
docker compose up -d system_monitor
```

### Run directly with Python

Run the script with Python:

```bash
python system_monitor/system_monitor.py
```

The script runs in an infinite loop, publishing and logging status updates every `SYSTEM_MONITOR_INTERVAL` seconds. Use Ctrl+C to stop gracefully.

## Output

### Local Logs
Logs are written to:

- `logs/<resolved-hostname>-htop-<HH.MM.SS>.log`
- console output

Log message body format:

```
[timestamp] Node ID: hostname-system_monitor, CPU: x%, Memory: used/total GB (%), Disk R/W: read/write KB/s, Network U/D: send/recv KB/s, Temp: x°C
```

`[timestamp]` is added by the logging formatter (`%(asctime)s`).

### ZeroMQ Published Data
Status data is published as JSON via ZeroMQ with the following structure:

```json
{
  "type": "system_status",
  "node_id": "hostname-system_monitor",
  "timestamp": "2026-02-24T12:34:56.123456",
  "cpu": 25.5,
  "memory_used_gb": 2.15,
  "memory_total_gb": 4.0,
  "memory_percent": 53.7,
  "disk_read_kbs": 123.45,
  "disk_write_kbs": 67.89,
  "network_send_kbs": 45.67,
  "network_recv_kbs": 89.12,
  "temperature": "55.0°C"
}
```

## Subscribing to Status Updates

Remote servers or nodes can subscribe to status updates using ZeroMQ SUB socket:

```python
import zmq
import json

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect('tcp://<system_monitor_ip>:5599')
socket.setsockopt_string(zmq.SUBSCRIBE, '')  # Subscribe to all messages

while True:
    status = socket.recv_json()
    print(status)
```

## Functions

### Helper Functions
- `get_cpu_status()`: Retrieves CPU usage percentage.
- `get_memory_status()`: Gets memory statistics (total, available, used, percent).
- `get_disk_status_static()`: Static disk usage snapshot (not used in main loop).
- `get_network_status_static()`: Static network counters (not used in main loop).
- `get_temperature_status()`: Fetches CPU temperature from sensors.
- `get_speeds()`: Calculates disk and network I/O speeds over `SYSTEM_MONITOR_INTERVAL`.

### SystemMonitor Class
- `__init__()`: Initializes ZMQNode, sets up publisher socket on `SYSTEM_MONITOR_PORT`.
- `publish_status()`: Publishes system metrics as JSON via ZeroMQ and logs locally.
- `run()`: Main loop that starts discovery, collects metrics, and publishes updates.

## Notes

- **Temperature Sensors**: Uses `psutil.sensors_temperatures()`. If sensors are not available, temperature shows an error message.
- **Discovery**: Inherits peer discovery from `ZMQNode` using `DISCOVERY_PORT_SYSTEM` (`50001`).
- **Raspberry Pi Specific**: Optimized for Raspberry Pi but works on any Linux system with appropriate sensors.
- **Graceful Shutdown**: Handles Ctrl+C (KeyboardInterrupt) to close sockets and clean up resources.
