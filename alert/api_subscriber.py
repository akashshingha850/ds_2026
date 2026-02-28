import requests
import json
import socket
import threading
import time
import logging
import os
from collections import deque
from datetime import datetime
import zmq
import sys

sys.path.append('.')
from alerting import AlertManager
from config import (
    DISCOVERY_BROADCAST,
    DISCOVERY_PORT,
    NODE_PORT,
    MOTION_FLAG_PORT,
    MOTION_IMAGE_PORT,
    DETECTION_COCO_PORT,
    SERVER_PORT
)

def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"

def discovery_loop(stop_event, peers_info, node_id, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind(("", DISCOVERY_PORT))
    except OSError as e:
        logging.warning(f"Discovery disabled: cannot bind UDP {DISCOVERY_PORT} ({e})")
        sock.close()
        return
    sock.settimeout(1.0)

    while not stop_event.is_set():
        try:
            sock.sendto(
                json.dumps(
                    {
                        "type": "discover",
                        "node_id": node_id,
                        "ip": get_local_ip(),
                        "port": port,
                    }
                ).encode("utf-8"),
                (DISCOVERY_BROADCAST, DISCOVERY_PORT),
            )

            data, addr = sock.recvfrom(4096)
            message = json.loads(data.decode("utf-8"))

            if message.get("node_id") != node_id and message.get("type") in {"discover", "announce"}:
                peer_id = message.get("node_id")
                if peer_id:
                    peers_info[peer_id] = {
                        "ip": message.get("ip") or addr[0],
                        "port": message.get("port", port),
                    }

                    if message.get("type") == "discover":
                        sock.sendto(
                            json.dumps({
                                "type": "announce",
                                "node_id": node_id,
                                "ip": get_local_ip(),
                                "port": port,
                            }).encode("utf-8"), (addr[0], DISCOVERY_PORT)
                        )
        except Exception:
            pass

        if peers_info:
            print(f"[Discovery:{node_id}] Known peers: {list(peers_info.keys())}")
        time.sleep(15 if peers_info else 2)

    sock.close()

def post_alert_to_api(message, api_url):
    """Send an alert payload to the optional external REST API."""
    if not api_url:
        return False

    event_type = message.get("type", "alert_notification")

    max_attempts = 3
    request_timeout_seconds = 10
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(api_url, json=message, timeout=request_timeout_seconds)
            if response.status_code == 200:
                logging.info(f"Successfully sent alert to API: {event_type}")
                return True
            logging.error(f"Failed to send alert to API (attempt {attempt}/{max_attempts}): {response.status_code} - {response.text}")
        except Exception as e:
            logging.error(f"Error sending alert to API (attempt {attempt}/{max_attempts}): {e}")

        if attempt < max_attempts:
            time.sleep(1.0)

    logging.error("External API unavailable after retries; continuing local alerting")
    return False


def build_alert_callback(api_url):
    def _on_alert(subject, body, json_payload):
        if not api_url:
            return

        serialized_payload = {}
        if isinstance(json_payload, dict):
            serialized_payload = dict(json_payload)
            serialized_payload.pop("image_bytes", None)

        outbound_message = {
            "type": "alert_notification",
            "subject": subject,
            "body": body,
            "alert": serialized_payload,
            "ts": datetime.now().isoformat(),
        }
        post_alert_to_api(outbound_message, api_url)

    return _on_alert


def process_aggregated_event(alert_manager, payload):
    try:
        alert_manager.process_event(payload)
    except Exception as e:
        logging.error(f"Alert processing error: {e}")


def subscriber_loop(context, peers_info, stop_event, alert_manager):
    sub_socket = context.socket(zmq.SUB)
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    detection_wait_seconds = 2.0
    connected_endpoints = set()
    message_count = 0
    current_events = {}
    pending_events = {}

    def connect_endpoint(ip, port, label):
        endpoint = f"tcp://{ip}:{port}"
        if endpoint in connected_endpoints:
            return
        sub_socket.connect(endpoint)
        connected_endpoints.add(endpoint)
        print(f"[SUB] Connected to {label} at {endpoint}")
        time.sleep(0.2)

    # Hybrid fallback: keep localhost endpoints connected as backup.
    connect_endpoint("127.0.0.1", MOTION_FLAG_PORT, "localhost-motion-flag")
    connect_endpoint("127.0.0.1", MOTION_IMAGE_PORT, "localhost-motion-image")
    connect_endpoint("127.0.0.1", DETECTION_COCO_PORT, "localhost-detection-coco")

    while not stop_event.is_set():
        try:
            now_monotonic = time.monotonic()

            # Flush stale pending events that did not receive detection in time.
            for sender, queue in list(pending_events.items()):
                while queue and queue[0]["deadline_monotonic"] <= now_monotonic:
                    expired_event = queue.popleft()
                    process_aggregated_event(alert_manager, expired_event["payload"])
                if not queue:
                    del pending_events[sender]

            for peer_id, info in peers_info.items():
                peer_ip = info.get("ip")
                if not peer_ip:
                    continue

                if peer_id.endswith("-motion"):
                    connect_endpoint(peer_ip, MOTION_FLAG_PORT, f"{peer_id}-flag")
                    connect_endpoint(peer_ip, MOTION_IMAGE_PORT, f"{peer_id}-image")
                elif peer_id.endswith("-detection_coco"):
                    connect_endpoint(peer_ip, DETECTION_COCO_PORT, peer_id)
                else:
                    connect_endpoint(peer_ip, info.get("port", NODE_PORT), peer_id)

            if sub_socket.poll(1000):
                recv_ts = datetime.now().isoformat()
                message = sub_socket.recv_json()
                message_count += 1
                sender = message.get("node_id", "unknown")
                print(f"[SUB] Received message #{message_count} from {sender}: {message.get('type')}")

                # Add receive timestamp
                message["recv_ts"] = recv_ts

                if message.get('type') == 'motion_flag':
                    if message.get('flag') == 1:
                        current_events[sender] = message
                    # Ignore flag == 0
                elif message.get('type') == 'detection_results':
                    source_sender = message.get("sender") or sender
                    sender_queue = pending_events.get(source_sender)
                    if sender_queue and len(sender_queue) > 0:
                        pending_event = sender_queue.popleft()
                        pending_event["payload"]["event"]["detection_results"] = message
                        pending_event["payload"]["event"]["metadata"]["detection_ts"] = message.get("ts")
                        process_aggregated_event(alert_manager, pending_event["payload"])
                        if not sender_queue:
                            del pending_events[source_sender]
                elif message.get('type') == 'image' and sender in current_events:
                    combined = {
                        'event': {
                            'motion_flag': current_events[sender],
                            'image': message,
                            'detection_results': None,
                            'metadata': {
                                'node_id': sender,
                                'event_ts': current_events[sender].get('ts'),
                                'image_ts': message.get('ts'),
                                'detection_ts': None,
                            }
                        }
                    }
                    if sender not in pending_events:
                        pending_events[sender] = deque()

                    pending_events[sender].append({
                        "payload": combined,
                        "deadline_monotonic": time.monotonic() + detection_wait_seconds,
                    })
                    del current_events[sender]

        except zmq.error.ContextTerminated:
            break
        except Exception as e:
            if not stop_event.is_set():
                print(f"[SUB] Error: {e}")
            connected_endpoints.clear()

    sub_socket.close()

if __name__ == "__main__":
    api_url = os.getenv("ALERT_SERVER_URL", f"http://localhost:{SERVER_PORT}/api/data").strip()
    if api_url == "":
        api_url = None

    node_id = f"{socket.gethostname()}-api-sub"

    context = zmq.Context()
    peers_info = {}
    stop_event = threading.Event()
    alert_manager = AlertManager(on_alert=build_alert_callback(api_url))

    sub_thread = threading.Thread(
        target=subscriber_loop,
        args=(context, peers_info, stop_event, alert_manager),
        daemon=True,
    )
    sub_thread.start()

    discovery_thread = threading.Thread(
        target=discovery_loop,
        args=(stop_event, peers_info, node_id, NODE_PORT),
        daemon=True,
    )
    discovery_thread.start()

    print(f"[SUB:{node_id}] Subscribing to messages on port {NODE_PORT}")
    print(f"[SUB:{node_id}] Local IP: {get_local_ip()}")
    if api_url:
        print(f"[SUB:{node_id}] Forwarding generated alerts to {api_url}\n")
    else:
        print(f"[SUB:{node_id}] External API forwarding disabled (local alerting only)\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")
    finally:
        stop_event.set()
        context.term()

