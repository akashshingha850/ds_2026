import json
import socket
import threading
import time
import logging
import os
from datetime import datetime, timedelta
import zmq
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.append(project_root)
from utils import resolve_device_hostname
from alerting import AlertManager
from config import (
    DISCOVERY_BROADCAST,
    DISCOVERY_PORT,
    NODE_PORT,
    MOTION_FLAG_PORT,
    MOTION_IMAGE_PORT,
    DETECTION_COCO_PORT,
    DETECTION_FIRE_PORT,
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
        print(f"[WARN] Discovery disabled: cannot bind UDP {DISCOVERY_PORT} ({e})")
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

def process_aggregated_event(alert_manager, payload):
    try:
        event = payload.get("event", {}) if isinstance(payload, dict) else {}
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        motion_flag = event.get("motion_flag", {}) if isinstance(event.get("motion_flag"), dict) else {}
        detection_results = event.get("detection_results", {}) if isinstance(event.get("detection_results"), dict) else {}
        detections = detection_results.get("detections", []) if isinstance(detection_results, dict) else []

        def _compute_queue_age_seconds(send_ts, recv_ts_iso):
            if not send_ts or send_ts == "unknown" or not recv_ts_iso:
                return None
            try:
                recv_dt = datetime.fromisoformat(recv_ts_iso)
                if "T" in str(send_ts):
                    send_dt = datetime.fromisoformat(send_ts)
                else:
                    try:
                        send_time = datetime.strptime(send_ts, "%H:%M:%S.%f").time()
                    except ValueError:
                        send_time = datetime.strptime(send_ts, "%H:%M:%S").time()
                    send_dt = datetime.combine(recv_dt.date(), send_time)
                    if send_dt > recv_dt:
                        send_dt = send_dt - timedelta(days=1)
                return (recv_dt - send_dt).total_seconds()
            except Exception:
                return None

        recv_ts = event.get("image", {}).get("recv_ts") or metadata.get("image_ts") or datetime.now().isoformat()
        event_ts = metadata.get("event_ts") or motion_flag.get("ts") or "unknown"
        detection_ts = metadata.get("detection_ts") or detection_results.get("ts")
        image_payload = event.get("image", {}) if isinstance(event.get("image"), dict) else {}
        image_id = image_payload.get("image_id") or detection_results.get("image_id")
        alert_send_ts = datetime.now().isoformat()
        queue_age_s = _compute_queue_age_seconds(event_ts, alert_send_ts)
        queue_age_text = f"{queue_age_s:.3f}s" if queue_age_s is not None else "unknown"
        node_id = metadata.get("node_id") or motion_flag.get("node_id") or "unknown-node"

        logging.info(
            f"[ALERT_PIPELINE] Node: {node_id} recieved Image #{image_id} - Event TS: {event_ts} - Recv TS: {recv_ts} - Detection TS: {detection_ts} "
            f"- Alert Send TS: {alert_send_ts} - Queue Age: {queue_age_text} - Detections: {len(detections)}"
        )

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
        logging.info(f"[API-SUB] Connected to {label} at {endpoint}")
        time.sleep(0.2)

    # Hybrid fallback: keep localhost endpoints connected as backup.
    connect_endpoint("127.0.0.1", MOTION_FLAG_PORT, "localhost-motion-flag")
    connect_endpoint("127.0.0.1", MOTION_IMAGE_PORT, "localhost-motion-image")
    connect_endpoint("127.0.0.1", DETECTION_COCO_PORT, "localhost-detection-coco")
    connect_endpoint("127.0.0.1", DETECTION_FIRE_PORT, "localhost-detection-fire")

    while not stop_event.is_set():
        try:
            now_monotonic = time.monotonic()

            # Flush stale pending events that did not receive detection in time.
            for event_key, pending_event in list(pending_events.items()):
                if pending_event["deadline_monotonic"] <= now_monotonic:
                    process_aggregated_event(alert_manager, pending_event["payload"])
                    del pending_events[event_key]

            for peer_id, info in peers_info.items():
                peer_ip = info.get("ip")
                if not peer_ip:
                    continue

                if peer_id.endswith("-motion"):
                    connect_endpoint(peer_ip, MOTION_FLAG_PORT, f"{peer_id}-flag")
                    connect_endpoint(peer_ip, MOTION_IMAGE_PORT, f"{peer_id}-image")
                elif peer_id.endswith("-detection_coco"):
                    connect_endpoint(peer_ip, DETECTION_COCO_PORT, peer_id)
                elif peer_id.endswith("-detection_fire"):
                    connect_endpoint(peer_ip, DETECTION_FIRE_PORT, peer_id)
                else:
                    connect_endpoint(peer_ip, info.get("port", NODE_PORT), peer_id)

            if sub_socket.poll(1000):
                recv_ts = datetime.now().isoformat()
                message = sub_socket.recv_json()
                message_count += 1
                sender = message.get("node_id", "unknown")
                message_image_id = message.get("image_id", "N/A")
                print(
                    f"[SUB: API_SUB] Received from {sender}: {message.get('type')} - Image #{message_image_id}"
                )

                # Add receive timestamp
                message["recv_ts"] = recv_ts

                if message.get('type') == 'motion_flag':
                    if message.get('flag') == 1:
                        current_events[sender] = message
                    # Ignore flag == 0
                elif message.get('type') == 'detection_results':
                    source_sender = message.get("sender") or sender
                    detection_image_id = message.get("image_id")
                    if detection_image_id is None:
                        print(
                            f"[API-SUB] detection_results from {source_sender} has no image_id; skipping correlation"
                        )
                        continue

                    event_key = (source_sender, str(detection_image_id))
                    pending_event = pending_events.pop(event_key, None)
                    if pending_event:
                        print(
                            f"[API-SUB] Correlated detection_results for sender={source_sender}, image_id={detection_image_id}"
                        )
                        pending_event["payload"]["event"]["detection_results"] = message
                        pending_event["payload"]["event"]["metadata"]["detection_ts"] = message.get("ts")
                        process_aggregated_event(alert_manager, pending_event["payload"])
                    else:
                        print(
                            f"[API-SUB] No pending event found for sender={source_sender}, image_id={detection_image_id}"
                        )
                elif message.get('type') == 'image' and sender in current_events:
                    image_id = message.get("image_id")
                    if image_id is None:
                        print(f"[API-SUB] image message from {sender} has no image_id; skipping")
                        continue

                    combined = {
                        'event': {
                            'motion_flag': current_events[sender],
                            'image': message,
                            'detection_results': None,
                            'metadata': {
                                'node_id': sender,
                                'event_ts': current_events[sender].get('ts'),
                                'image_ts': message.get('ts'),
                                'image_id': image_id,
                                'detection_ts': None,
                            }
                        }
                    }

                    event_key = (sender, str(image_id))
                    pending_events[event_key] = {
                        "payload": combined,
                        "deadline_monotonic": time.monotonic() + detection_wait_seconds,
                    }
                    print(f"[API-SUB] Queued image event for sender={sender}, image_id={image_id}")
                    del current_events[sender]

        except zmq.error.ContextTerminated:
            break
        except Exception as e:
            if not stop_event.is_set():
                print(f"[ERROR][SUB] {e}")
            connected_endpoints.clear()

    sub_socket.close()

if __name__ == "__main__":
    node_id = f"{resolve_device_hostname()}-api-sub"

    context = zmq.Context()
    peers_info = {}
    stop_event = threading.Event()
    alert_manager = AlertManager()

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

    logging.info(f"[SUB:{node_id}] Subscribing to messages on port {NODE_PORT}")
    logging.info(f"[SUB:{node_id}] Local IP: {get_local_ip()}")
    logging.info(f"[SUB:{node_id}] Alert forwarding is Telegram/Webhook only")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[INFO] Shutting down...")
    finally:
        stop_event.set()
        context.term()

