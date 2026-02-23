import socket
import os
import threading
import time
import json
import logging
import zmq
import sys
from datetime import datetime

# aiuBSOIBO
# Add parent directory to path to import config
sys.path.append('.')

from config import (
    DISCOVERY_BROADCAST,
    DISCOVERY_PORT,
)


def resolve_device_hostname():
    try:
        with open('/host_hostname', 'r') as f:
            host_name = f.read().strip()
            if host_name:
                return host_name
    except Exception:
        pass

    try:
        with open('/etc/hostname', 'r') as f:
            host_name = f.read().strip()
            if host_name:
                return host_name
    except Exception:
        pass

    return socket.gethostname()

# Ensure logs directory exists and configure logging to hostname-specific file
os.makedirs('logs', exist_ok=True)
device_hostname = resolve_device_hostname()
logging.basicConfig(
    filename=f"logs/{device_hostname}.log",
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    force=True,
)
# Add console handler
root_logger = logging.getLogger('')
has_stream_handler = any(
    isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
    for handler in root_logger.handlers
)
if not has_stream_handler:
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    root_logger.addHandler(console)

class ZMQNode:
    def dynamic_peer_subscription(self, suffix, fallback_port, sub_socket, poll_timeout=1000, discovery_interval=30, fallback_host="localhost"):
        """
        Periodically re-discover peer by suffix and switch subscription if peer changes.
        Args:
            suffix: Peer node_id suffix to discover (e.g., '-motion')
            fallback_port: Port to use for localhost fallback
            sub_socket: ZMQ SUB socket to manage connections
            poll_timeout: Poll timeout in ms for receiving messages
            discovery_interval: Seconds between peer re-discovery attempts
        """
        if not hasattr(self, "_dynamic_sub_state"):
            self._dynamic_sub_state = {}

        state_key = (id(sub_socket), suffix, fallback_port, fallback_host)
        state = self._dynamic_sub_state.get(state_key)
        if state is None:
            state = {
                "current_peer": None,
                "current_endpoint": None,
                "last_discovery_time": 0.0,
            }
            self._dynamic_sub_state[state_key] = state

        now = time.time()
        if (state["current_peer"] is None) or (now - state["last_discovery_time"] > discovery_interval):
            discovery_timeout = 10 if state["current_peer"] is None else 1
            discovered_peer = self.discover_peer_by_suffix(
                suffix=suffix,
                timeout=discovery_timeout,
                fallback_to_localhost=True,
                fallback_port=fallback_port,
                fallback_host=fallback_host
            )
            state["last_discovery_time"] = now

            if discovered_peer is None:
                print(f"[SUB] No peer with suffix '{suffix}' found")
                return None

            peer_ip = discovered_peer.get('ip', fallback_host)
            peer_port = discovered_peer.get('port', fallback_port)
            next_endpoint = f"tcp://{peer_ip}:{peer_port}"

            if state["current_endpoint"] != next_endpoint:
                if state["current_endpoint"]:
                    sub_socket.disconnect(state["current_endpoint"])
                sub_socket.connect(next_endpoint)
                print(f"[SUB] Connected to {next_endpoint}")
                state["current_endpoint"] = next_endpoint
                state["current_peer"] = discovered_peer

        if sub_socket.poll(poll_timeout):
            return sub_socket.recv_json()

        return None
    def __init__(self, node_suffix, discovery_port=None):
        self.node_id = f"{resolve_device_hostname()}-{node_suffix}"

        # Try to get real IP from host network
        self.context = zmq.Context()
        self.peers_info = {}
        self.stop_event = threading.Event()
        ip_env = os.environ.get('HOST_IP')
        self.local_ip = ip_env if ip_env else self.get_local_ip()
        # Calculate subnet broadcast assuming /24
        ip_parts = self.local_ip.split('.')
        if len(ip_parts) == 4:
            self.broadcast_addr = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
        else:
            self.broadcast_addr = "255.255.255.255"  # fallback
        self.discovery_port = discovery_port or DISCOVERY_PORT

    def get_local_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"

    def discovery_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(("", self.discovery_port))
        except OSError as e:
            logging.warning(f"Discovery port {self.discovery_port} already in use: {e}. Skipping discovery.")
            sock.close()
            return
        sock.settimeout(1.0)

        while not self.stop_event.is_set():
            try:
                sock.sendto(
                    json.dumps(
                        {
                            "type": "discover",
                            "node_id": self.node_id,
                            "ip": self.local_ip,
                            "port": getattr(self, 'pub_port', 0),
                        }
                    ).encode("utf-8"),
                    (self.broadcast_addr, self.discovery_port),
                )

                data, addr = sock.recvfrom(4096)
                message = json.loads(data.decode("utf-8"))

                if message.get("node_id") != self.node_id and message.get("type") in {"discover", "announce"}:
                    peer_id = message.get("node_id")
                    if peer_id:
                        self.peers_info[peer_id] = {
                            "ip": message.get("ip") or addr[0],
                            "port": message.get("port", 0),
                        }

                        if message.get("type") == "discover":
                            sock.sendto(
                                json.dumps({
                                    "type": "announce",
                                    "node_id": self.node_id,
                                    "ip": self.local_ip,
                                    "port": getattr(self, 'pub_port', 0),
                                }).encode("utf-8"), (addr[0], self.discovery_port)
                            )
            except Exception:
                pass

            if self.peers_info:
                print(f"[Discovery:{self.node_id}] Known peers: {list(self.peers_info.keys())}")
            time.sleep(15 if self.peers_info else 2)

        sock.close()

    def discover_peer_by_suffix(self, suffix, timeout=30, fallback_to_localhost=False, fallback_port=0, fallback_host="localhost"):
        """
        Discover a peer by node_id suffix (e.g., '-motion', '-system_monitor').
        
        Args:
            suffix: The suffix to match in peer node_id (e.g., '-motion')
            timeout: Seconds to wait for discovery before fallback
            fallback_to_localhost: If True, return localhost after timeout
            fallback_port: Port to use for localhost fallback
        
        Returns:
            dict with 'ip' and 'port', or None if not found
        """
        # Give discovery thread time to do initial broadcast/receive
        print(f"[Discovery:{self.node_id}] Waiting for peer with suffix '{suffix}'...")
        time.sleep(1)
        
        start_time = time.time()
        
        while not self.stop_event.is_set():
            # Check discovered peers
            for peer_id, peer_info in self.peers_info.items():
                if peer_id.endswith(suffix):
                    logging.info(f"[Discovery:{self.node_id}] Found remote peer: {peer_id} at {peer_info['ip']}")
                    return peer_info
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                if fallback_to_localhost:
                    print(f"[Discovery:{self.node_id}] No remote peer found, using {fallback_host}")
                    return {'ip': fallback_host, 'port': fallback_port}
                else:
                    logging.warning(f"[Discovery:{self.node_id}] No peer with suffix '{suffix}' found after {timeout}s")
                    return None
            
            time.sleep(2)
        
        return None

    def start_discovery(self):
        discovery_thread = threading.Thread(target=self.discovery_loop, daemon=True)
        discovery_thread.start()

    def cleanup(self):
        self.stop_event.set()
        self.context.term()