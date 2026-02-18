# System Monitor

## Overview

`system_monitor.py` is a Python script that continuously monitors and logs system status information for a node in the distributed system. It extends the `ZMQNode` class from `utils.py` to provide peer discovery and ZeroMQ-based broadcasting of system metrics. The script collects metrics such as CPU usage, memory usage, disk I/O speeds, network I/O speeds, and CPU temperature, then publishes them via ZeroMQ while also logging locally to both a hostname-based file (`logs/<hostname>.log`) and the console.

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
- `config.py`: Imports `SYSTEM_MONITOR_INTERVAL` and `SYSTEM_MONITOR_PORT`.
- `utils.py`: Provides `ZMQNode` base class with discovery and cleanup.

## Configuration

Configuration values from `config.py`:
- `SYSTEM_MONITOR_INTERVAL`: Time interval (in seconds) over which speeds are calculated and between status updates (default: 1).
- `SYSTEM_MONITOR_PORT`: ZeroMQ port for publishing status data (default: 5559).

## Usage

### Run with Docker scripts (recommended)

From the project root:

```bash
./build_system_monitor.sh
./run_system_monitor.sh
```

The run script starts the container in detached mode with:
- image name: `system_monitor`
- container name: `system_monitor`
- host networking: `--network host`
- logs volume: `./logs:/app/logs`

If a previous container exists with another name, stop and remove it before rerunning:

```bash
docker stop <old_container_name>
docker rm <old_container_name>
```

### Run directly with Python

Run the script with Python:

```bash
python system_monitor.py
```

The script runs in an infinite loop, publishing and logging status updates every `SYSTEM_MONITOR_INTERVAL` seconds. Use Ctrl+C to stop gracefully.

## Output

### Local Logs
Logs are written to `logs/<hostname>.log` and console in the following format:

```
[timestamp] Node ID: hostname-system_monitor, CPU: x%, Memory: used/total GB (%), Disk R/W: read/write KB/s, Network U/D: send/recv KB/s, Temp: x°C
```

### ZeroMQ Published Data
Status data is published as JSON via ZeroMQ with the following structure:

```json
{
  "type": "system_status",
  "node_id": "hostname-system_monitor",
  "timestamp": "2026-02-13 12:34:56",
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
socket.connect('tcp://192.168.192.180:5559')  # Connect to Pi's IP and SYSTEM_MONITOR_PORT
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
- **Discovery**: Inherits peer discovery from `ZMQNode`, broadcasting node presence on UDP port 50000.
- **Raspberry Pi Specific**: Optimized for Raspberry Pi but works on any Linux system with appropriate sensors.
- **Graceful Shutdown**: Handles Ctrl+C (KeyboardInterrupt) to close sockets and clean up resources.

## Troubleshooting

- **Docker API 500 / desktop socket error**: If `docker ps` shows an error containing `/home/.../.docker/desktop/docker.sock`, reset Docker host env:

```bash
unset DOCKER_HOST
export DOCKER_HOST=unix:///var/run/docker.sock
docker ps
```
