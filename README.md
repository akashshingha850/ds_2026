# ZeroMQ Communication Test - 3 Raspberry Pi Devices

Simple test to verify ZeroMQ communication between gateway and 3 edge devices.

## Docker hostname and logs

When running via Docker Compose, each service mounts the host `/etc/hostname` file as `/host_hostname` (read-only). The shared logger uses this value for the log filename, so logs are grouped per device (for example: `logs/my-pi-hostname.log`) without hardcoding environment variables.

## Setup

### Alert Telegram settings via env file

1. Create the env file from template:

```bash
cp .env.example .env
```

2. Edit `.env` and set your real values:

```env
ALERT_TELEGRAM_ENABLED=true
ALERT_TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
ALERT_TELEGRAM_CHAT_ID=YOUR_TELEGRAM_CHAT_ID
ALERT_TELEGRAM_ATTACH_IMAGE=true
```

3. Deploy as usual. `deploy_stack.sh` loads `.env` before `docker stack deploy`.

### 1. Install ZeroMQ on all Raspberry Pis

```bash
sudo apt-get update
sudo apt-get install libzmq3-dev
pip3 install pyzmq
```

Or use requirements.txt:
```bash
pip3 install -r requirements.txt
```

### 2. Configure Network

Edit `config.py` and set `GATEWAY_IP` to your gateway Raspberry Pi's IP address:
```python
GATEWAY_IP = "192.168.1.100"  # Change this!
```

Find your IP with: `hostname -I`

### 3. Open Firewall Ports (if needed)

On the gateway:
```bash
sudo ufw allow 5555/tcp
sudo ufw allow 5556/tcp
```

## Running the Test

### On Gateway Raspberry Pi:
```bash
python3 gateway.py
```

### On Edge Device 1:
```bash
python3 edge_device.py edge_1
```

### On Edge Device 2:
```bash
python3 edge_device.py edge_2
```

### On Edge Device 3:
```bash
python3 edge_device.py edge_3
```

## Expected Output

**Gateway will:**
- Send 3 test messages
- Receive 3 responses (one from each device)
- Display all received responses

**Each Edge Device will:**
- Receive a message from gateway
- Process it
- Send a response back

## Testing Locally (Same Machine)

For testing on one machine, use `127.0.0.1` as `GATEWAY_IP`:

```bash
# Terminal 1 - Gateway
python3 gateway.py

# Terminal 2 - Edge 1
python3 edge_device.py edge_1

# Terminal 3 - Edge 2
python3 edge_device.py edge_2

# Terminal 4 - Edge 3
python3 edge_device.py edge_3
```

## Troubleshooting

**Connection refused:**
- Check `GATEWAY_IP` in config.py
- Verify gateway is running first
- Check firewall: `sudo ufw status`

**No response:**
- Make sure all 3 edge devices are running
- Check network connectivity: `ping <gateway_ip>`

## How It Works

```
Gateway (PUSH:5555) ──> Edge Devices (PULL)
                         │
                         │ Process
                         ▼
Gateway (PULL:5556) <── Edge Devices (PUSH)
```

The gateway sends messages using PUSH socket, edge devices receive with PULL socket, process, and respond back using PUSH to gateway's PULL socket.
