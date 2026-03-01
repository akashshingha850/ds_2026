import base64
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta

import cv2
import numpy as np
import requests
import zmq
import sys

# Setup imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from utils import resolve_device_hostname, ZMQNode
from config import (
    ALERTS_ENABLED,
    ALERT_COOLDOWN_SECONDS,
    ALERT_DRY_RUN,
    ALERT_TELEGRAM_ENABLED,
    ALERT_TELEGRAM_ATTACH_IMAGE,
    ALERT_TELEGRAM_BOT_TOKEN,
    ALERT_TELEGRAM_CHAT_ID,
    ALERT_WEBHOOK_ENABLED,
    ALERT_WEBHOOK_URL,
    NODE_PORT,
    MOTION_FLAG_PORT,
    MOTION_IMAGE_PORT,
    DETECTION_COCO_PORT,
    DETECTION_FIRE_PORT,
)

ALERT_TELEGRAM_BOT_TOKEN="8680352976:AAE1QES_Nn4JCwSl6EIRlfo3BAX-8B8eCqw"
ALERT_TELEGRAM_CHAT_ID=6057187917
ALERT_TELEGRAM_ATTACH_IMAGE=True

class AlertManager:
    def __init__(self, on_alert=None):
        self.node_id = resolve_device_hostname()
        self.enabled = ALERTS_ENABLED
        self.dry_run = ALERT_DRY_RUN
        self.on_alert = on_alert
        self.lock = threading.Lock()
        self.recent_alerts = {}

        self.telegram_enabled = ALERT_TELEGRAM_ENABLED
        self.telegram_attach_image = ALERT_TELEGRAM_ATTACH_IMAGE
        self.telegram_bot_token = os.getenv("ALERT_TELEGRAM_BOT_TOKEN", ALERT_TELEGRAM_BOT_TOKEN)
        self.telegram_chat_id = os.getenv("ALERT_TELEGRAM_CHAT_ID", ALERT_TELEGRAM_CHAT_ID)

        self.webhook_enabled = ALERT_WEBHOOK_ENABLED
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL", ALERT_WEBHOOK_URL)

    def _decode_image(self, image_payload):
        if not isinstance(image_payload, dict):
            return None
        image_b64 = image_payload.get("image_data")
        if not isinstance(image_b64, str) or not image_b64:
            return None
        try:
            frame = cv2.imdecode(np.frombuffer(base64.b64decode(image_b64), dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                return None
            ok, encoded = cv2.imencode(".jpg", frame)
            return encoded.tobytes() if ok else None
        except Exception:
            return None

    def _extract_triggered_classes(self, detections):
        classes = set()
        for item in detections:
            if isinstance(item, dict):
                classes.add(str(item.get("class", "unknown")).lower())
        return sorted(classes)

    def _was_sent_recently(self, node_id, triggered_classes, now):
        key = f"{node_id}|{','.join(triggered_classes)}"
        with self.lock:
            last_sent = self.recent_alerts.get(key)
            self.recent_alerts[key] = now
        return last_sent is not None and (now - last_sent) < ALERT_COOLDOWN_SECONDS

    def _pass_summary_data(self, event_ts, node_id, triggered_classes):
        payload = {
            "timestamp": event_ts,
            "node": node_id,
            "triggered_classes": triggered_classes,
        }
        if callable(self.on_alert):
            try:
                self.on_alert("[ALERT SUMMARY]", "summary", payload)
            except Exception:
                pass

    def process_event(self, payload):
        if not self.enabled:
            return

        event = payload.get("event", {}) if isinstance(payload, dict) else {}
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        motion_flag = event.get("motion_flag", {}) if isinstance(event.get("motion_flag"), dict) else {}
        detection_results = event.get("detection_results", {}) if isinstance(event.get("detection_results"), dict) else {}
        detections = detection_results.get("detections", []) if isinstance(detection_results, dict) else []

        node_id = metadata.get("node_id") or motion_flag.get("node_id") or "unknown-node"
        event_ts = metadata.get("event_ts") or motion_flag.get("ts") or "unknown-ts"
        triggered_classes = self._extract_triggered_classes(detections)

        if not triggered_classes:
            return

        now = time.monotonic()
        if self._was_sent_recently(node_id, triggered_classes, now):
            self._pass_summary_data(event_ts, node_id, triggered_classes)
            return

        image_payload = event.get("image", {}) if isinstance(event.get("image"), dict) else {}
        image_bytes = self._decode_image(image_payload)
        payload_out = {
            "type": "immediate",
            "severity": "standard",
            "node_id": node_id,
            "event_ts": event_ts,
            "trigger_classes": [{"class": name, "severity": "standard"} for name in triggered_classes],
            "detected_classes": [{"class": name} for name in triggered_classes],
            "image_bytes": image_bytes,
        }
        subject = f"[ALERT:STANDARD] {', '.join(triggered_classes)} on {node_id}"
        body = (
            f"Type: immediate\n"
            f"Severity: standard\n"
            f"Node: {node_id}\n"
            f"Trigger Classes: {', '.join(triggered_classes)}\n"
            f"Event TS: {event_ts}"
        )
        self._dispatch(subject, body, payload_out)

    def _dispatch(self, subject, body, json_payload):
        if self.dry_run:
            return

        send_ts = datetime.now().isoformat()
        payload_copy = dict(json_payload) if isinstance(json_payload, dict) else {}
        image_bytes = payload_copy.pop("image_bytes", None)
        payload_copy["alert_send_ts"] = send_ts
        payload_copy["image_attached"] = bool(image_bytes)
        payload_text = json.dumps(payload_copy, ensure_ascii=False)
        logging.info(
            f" {self.node_id} SENT ALERT -  Send TS: {send_ts} - Subject: {subject} - Payload: {payload_text}"
        )

        if callable(self.on_alert):
            try:
                self.on_alert(subject, body, json_payload)
            except Exception:
                pass

        if self.telegram_enabled:
            self._send_telegram(
                subject=subject,
                body=body,
                image_bytes=json_payload.get("image_bytes") if isinstance(json_payload, dict) else None,
            )
        if self.webhook_enabled:
            self._send_webhook(json_payload)

    def _send_telegram(self, subject, body, image_bytes=None):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return

        caption = f"{subject}\n\n{body}"
        base_url = f"https://api.telegram.org/bot{self.telegram_bot_token}"

        try:
            if self.telegram_attach_image and image_bytes:
                response = requests.post(
                    f"{base_url}/sendPhoto",
                    data={"chat_id": self.telegram_chat_id, "caption": caption[:1024]},
                    files={"photo": ("alert_image.jpg", image_bytes, "image/jpeg")},
                    timeout=10,
                )
            else:
                response = requests.post(
                    f"{base_url}/sendMessage",
                    json={"chat_id": self.telegram_chat_id, "text": caption},
                    timeout=10,
                )
            if response.status_code != 200:
                logging.error(f"Telegram alert failed: {response.status_code} {response.text}")
            else:
                logging.info(f"[ALERT_SEND] Telegram sent successfully - status={response.status_code}")
        except Exception as exc:
            logging.error(f"Telegram alert failed: {exc}")

    def _send_webhook(self, payload):
        if not self.webhook_url:
            return
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if not (200 <= response.status_code < 300):
                logging.error(f"Webhook alert failed: {response.status_code} {response.text}")
            else:
                logging.info(f"[ALERT_SEND] Webhook sent successfully - status={response.status_code}")
        except Exception as exc:
            logging.error(f"Webhook alert failed: {exc}")


class AlertNode(ZMQNode):
    def __init__(self):
        super().__init__("api-sub")
        self.alert_manager = AlertManager()
        self.connected_endpoints = set()

    def process_aggregated_event(self, payload):
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

            self.alert_manager.process_event(payload)
        except Exception as e:
            logging.error(f"Alert processing error: {e}")

    def connect_endpoint(self, sub_socket, ip, port, label):
        endpoint = f"tcp://{ip}:{port}"
        if endpoint in self.connected_endpoints:
            return
        sub_socket.connect(endpoint)
        self.connected_endpoints.add(endpoint)
        logging.info(f"[SUB] Connected to {label} at {endpoint}")
        time.sleep(0.2)

    def subscriber_loop(self):
        sub_socket = self.context.socket(zmq.SUB)
        sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        detection_wait_seconds = 2.0
        message_count = 0
        current_events = {}
        pending_events = {}

        # Hybrid fallback: keep localhost endpoints connected as backup.
        self.connect_endpoint(sub_socket, "127.0.0.1", MOTION_FLAG_PORT, "localhost-motion-flag")
        self.connect_endpoint(sub_socket, "127.0.0.1", MOTION_IMAGE_PORT, "localhost-motion-image")
        self.connect_endpoint(sub_socket, "127.0.0.1", DETECTION_COCO_PORT, "localhost-detection-coco")
        self.connect_endpoint(sub_socket, "127.0.0.1", DETECTION_FIRE_PORT, "localhost-detection-fire")

        while not self.stop_event.is_set():
            try:
                now_monotonic = time.monotonic()

                # Flush stale pending events that did not receive detection in time.
                for event_key, pending_event in list(pending_events.items()):
                    if pending_event["deadline_monotonic"] <= now_monotonic:
                        self.process_aggregated_event(pending_event["payload"])
                        del pending_events[event_key]

                # Dynamically connect to discovered peers' specific ports
                for peer_id, info in list(self.peers_info.items()):
                    peer_ip = info.get("ip")
                    if not peer_ip:
                        continue

                    if peer_id.endswith("-motion"):
                        self.connect_endpoint(sub_socket, peer_ip, MOTION_FLAG_PORT, f"{peer_id}-flag")
                        self.connect_endpoint(sub_socket, peer_ip, MOTION_IMAGE_PORT, f"{peer_id}-image")
                    elif peer_id.endswith("-detection_coco"):
                        self.connect_endpoint(sub_socket, peer_ip, DETECTION_COCO_PORT, peer_id)
                    elif peer_id.endswith("-detection_fire"):
                        self.connect_endpoint(sub_socket, peer_ip, DETECTION_FIRE_PORT, peer_id)
                    else:
                        self.connect_endpoint(sub_socket, peer_ip, info.get("port", NODE_PORT), peer_id)

                if sub_socket.poll(1000):
                    recv_ts = datetime.now().isoformat()
                    message = sub_socket.recv_json()
                    message_count += 1
                    sender = message.get("node_id", "unknown")
                    message_image_id = message.get("image_id", "N/A")
                    logging.info(f"[SUB] Received message #{message_count} from {sender}: {message.get('type')} - Image #{message_image_id}")

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
                            logging.warning(f"[SUB] detection_results from {source_sender} has no image_id; skipping correlation")
                            continue

                        event_key = (source_sender, str(detection_image_id))
                        pending_event = pending_events.pop(event_key, None)
                        if pending_event:
                            logging.info(f"[SUB] Correlated detection_results for sender={source_sender}, image_id={detection_image_id}")
                            pending_event["payload"]["event"]["detection_results"] = message
                            pending_event["payload"]["event"]["metadata"]["detection_ts"] = message.get("ts")
                            self.process_aggregated_event(pending_event["payload"])
                        else:
                            logging.warning(f"[SUB] No pending event found for sender={source_sender}, image_id={detection_image_id}")
                    elif message.get('type') == 'image' and sender in current_events:
                        image_id = message.get("image_id")
                        if image_id is None:
                            logging.warning(f"[SUB] image message from {sender} has no image_id; skipping")
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
                        logging.info(f"[SUB] Queued image event for sender={sender}, image_id={image_id}")
                        del current_events[sender]

            except zmq.error.ContextTerminated:
                break
            except Exception as e:
                if not self.stop_event.is_set():
                    logging.error(f"[SUB] Error: {e}")

        sub_socket.close()

    def run(self):
        # Start Discovery Loop (from inherited ZMQNode)
        self.start_discovery()
        
        logging.info(f"[SUB:{self.node_id}] Subscribing to messages on port {NODE_PORT}")
        logging.info(f"[SUB:{self.node_id}] Local IP: {self.local_ip}")
        logging.info(f"[SUB:{self.node_id}] Alert forwarding is Telegram/Webhook only")

        # Run subscriber logic on main thread
        try:
            self.subscriber_loop()
        except KeyboardInterrupt:
            logging.info("[INFO] Shutting down...")
        finally:
            self.cleanup()

if __name__ == "__main__":
    node = AlertNode()
    node.run()
