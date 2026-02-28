import logging
import os
import sys
import threading
import time
import base64
from datetime import datetime
import numpy as np
import cv2

import requests

sys.path.append('.')
import utils
from config import (
    ALERTS_ENABLED,
    ALERT_CLASS_WHITELIST,
    ALERT_COOLDOWN_SECONDS,
    ALERT_DIGEST_WINDOW_SECONDS,
    ALERT_DRY_RUN,
    ALERT_NEW_OBJECT_ONLY,
    ALERT_OBJECT_INACTIVE_SECONDS,
    ALERT_EXCLUDED_NODE_PREFIXES,
    ALERT_FIRST_HIT_IMMEDIATE,
    ALERT_IMMEDIATE_CLASSES,
    ALERT_MIN_CONFIDENCE,
    ALERT_REQUIRE_DETECTIONS,
    ALERT_REQUIRE_MOTION_FLAG,
    ALERT_TELEGRAM_ENABLED,
    ALERT_TELEGRAM_ATTACH_IMAGE,
    ALERT_TELEGRAM_BOT_TOKEN,
    ALERT_TELEGRAM_CHAT_ID,
    ALERT_WEBHOOK_ENABLED,
    ALERT_WEBHOOK_URL,
)


class AlertManager:
    def __init__(self, on_alert=None):
        self.enabled = ALERTS_ENABLED
        self.dry_run = ALERT_DRY_RUN
        self.first_hit_immediate = ALERT_FIRST_HIT_IMMEDIATE
        self.on_alert = on_alert
        self.lock = threading.Lock()
        self.cooldown_until = {}
        self.digest_buffer = {}
        self.last_digest_sent = time.monotonic()
        self.last_seen_class = {}
        self.previous_classes_by_node = {}
        self.whitelist_set = {name.lower() for name in ALERT_CLASS_WHITELIST}
        self.immediate_class_set = {name.lower() for name in ALERT_IMMEDIATE_CLASSES}
        self.excluded_node_prefixes = tuple(ALERT_EXCLUDED_NODE_PREFIXES)
        self.new_object_only = ALERT_NEW_OBJECT_ONLY
        self.object_inactive_seconds = ALERT_OBJECT_INACTIVE_SECONDS

        self.telegram_enabled = ALERT_TELEGRAM_ENABLED
        self.telegram_attach_image = ALERT_TELEGRAM_ATTACH_IMAGE
        self.telegram_bot_token = os.getenv("ALERT_TELEGRAM_BOT_TOKEN", ALERT_TELEGRAM_BOT_TOKEN)
        self.telegram_chat_id = os.getenv("ALERT_TELEGRAM_CHAT_ID", ALERT_TELEGRAM_CHAT_ID)

        self.webhook_enabled = ALERT_WEBHOOK_ENABLED
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL", ALERT_WEBHOOK_URL)

    def _decode_event_image_for_attachment(self, image_payload):
        if not isinstance(image_payload, dict):
            return None

        image_b64 = image_payload.get("image_data")
        if not isinstance(image_b64, str) or not image_b64:
            return None

        try:
            jpeg_bytes = base64.b64decode(image_b64)
        except Exception:
            return None

        frame = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return None

        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            return None

        return encoded.tobytes()

    def _compute_queue_age_seconds(self, send_ts, recv_ts_iso):
        if not send_ts or send_ts == "unknown" or not recv_ts_iso:
            return None
        try:
            send_dt = datetime.fromisoformat(send_ts)
            recv_dt = datetime.fromisoformat(recv_ts_iso)
            return (recv_dt - send_dt).total_seconds()
        except Exception:
            return None

    def process_event(self, payload):
        if not self.enabled:
            return

        event = payload.get("event", {}) if isinstance(payload, dict) else {}
        motion_flag = event.get("motion_flag", {}) if isinstance(event.get("motion_flag"), dict) else {}
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        detection_results = event.get("detection_results", {}) if isinstance(event.get("detection_results"), dict) else {}
        detections = detection_results.get("detections", []) if isinstance(detection_results, dict) else []

        if ALERT_REQUIRE_MOTION_FLAG and motion_flag.get("flag") != 1:
            return

        if ALERT_REQUIRE_DETECTIONS and not detections:
            return

        node_id = metadata.get("node_id") or motion_flag.get("node_id") or "unknown-node"
        if isinstance(node_id, str) and node_id.startswith(self.excluded_node_prefixes):
            return

        event_ts = metadata.get("event_ts") or motion_flag.get("ts") or "unknown-ts"
        image_payload = event.get("image", {}) if isinstance(event.get("image"), dict) else {}
        image_bytes = self._decode_event_image_for_attachment(image_payload)

        image_id = image_payload.get("image_id", None)
        sender = image_payload.get("node_id", node_id)
        send_ts = image_payload.get("ts", "unknown")
        recv_ts = image_payload.get("recv_ts", metadata.get("recv_ts", "unknown"))
        detection_ts = metadata.get("detection_ts") or detection_results.get("ts") or "unknown"
        decode_ms = float(detection_results.get("decode_ms", 0.0) or 0.0)
        inference_ms = float(detection_results.get("inference_ms", 0.0) or 0.0)
        queue_age_s = self._compute_queue_age_seconds(send_ts, recv_ts)
        queue_age_text = f"{queue_age_s:.3f}s" if queue_age_s is not None else "unknown"

        logging.info(
            f"{node_id} received image #{image_id} from {sender} - Send TS: {send_ts} - Recv TS: {recv_ts} - Detect TS: {detection_ts} "
            f"- Queue Age: {queue_age_text} - Decode: {decode_ms:.2f}ms - Inference: {inference_ms:.2f}ms - Results: {len(detections)} detections"
        )

        now = time.monotonic()
        immediate_payloads = []
        current_classes = set()
        detected_entries = []

        class_confidence_map = {}
        for detection in detections:
            if not isinstance(detection, dict):
                continue
            class_name = str(detection.get("class", "unknown")).lower()
            confidence = float(detection.get("confidence", 0.0))
            current = class_confidence_map.get(class_name)
            if current is None or confidence > current:
                class_confidence_map[class_name] = confidence

        for class_name, confidence in class_confidence_map.items():

            if confidence < ALERT_MIN_CONFIDENCE:
                continue

            if self.whitelist_set and class_name not in self.whitelist_set:
                continue

            current_classes.add(class_name)
            detected_entries.append({
                "class": class_name,
                "confidence": confidence,
            })

        previous_classes = self.previous_classes_by_node.get(node_id, set())

        for class_name, confidence in class_confidence_map.items():

            if confidence < ALERT_MIN_CONFIDENCE:
                continue

            if self.whitelist_set and class_name not in self.whitelist_set:
                continue

            dedup_key = f"{node_id}:{class_name}"

            with self.lock:
                last_seen = self.last_seen_class.get(dedup_key)
                self.last_seen_class[dedup_key] = now

                if self.new_object_only:
                    was_in_previous = class_name in previous_classes
                    is_recent = last_seen is not None and (now - last_seen) < self.object_inactive_seconds
                    if was_in_previous and is_recent:
                        continue

                if not self.new_object_only and last_seen is not None and (now - last_seen) < self.object_inactive_seconds:
                    continue

                cooldown_expires = self.cooldown_until.get(dedup_key, 0)
                if now < cooldown_expires:
                    continue
                self.cooldown_until[dedup_key] = now + ALERT_COOLDOWN_SECONDS

            if class_name in self.immediate_class_set:
                immediate_payloads.append({
                    "type": "immediate",
                    "severity": "emergency",
                    "node_id": node_id,
                    "class": class_name,
                    "confidence": confidence,
                    "event_ts": event_ts,
                    "image_bytes": image_bytes,
                })
            elif self.first_hit_immediate:
                immediate_payloads.append({
                    "type": "immediate",
                    "severity": "standard",
                    "node_id": node_id,
                    "class": class_name,
                    "confidence": confidence,
                    "event_ts": event_ts,
                    "image_bytes": image_bytes,
                })
            else:
                self._queue_digest_item(
                    dedup_key=dedup_key,
                    node_id=node_id,
                    class_name=class_name,
                    confidence=confidence,
                    event_ts=event_ts,
                )

        self.previous_classes_by_node[node_id] = current_classes

        if immediate_payloads:
            severity = "emergency" if any(item["severity"] == "emergency" for item in immediate_payloads) else "standard"
            trigger_entries = [
                {
                    "class": item["class"],
                    "confidence": item["confidence"],
                    "severity": item["severity"],
                }
                for item in immediate_payloads
            ]
            trigger_classes = ", ".join(entry["class"] for entry in trigger_entries)
            all_classes = ", ".join(f"{entry['class']} ({entry['confidence']:.2f})" for entry in detected_entries)
            trigger_classes_with_conf = ", ".join(f"{entry['class']} ({entry['confidence']:.2f})" for entry in trigger_entries)

            payload = {
                "type": "immediate",
                "severity": severity,
                "node_id": node_id,
                "event_ts": event_ts,
                "trigger_classes": trigger_entries,
                "detected_classes": detected_entries,
                "image_bytes": image_bytes,
            }
            subject = f"[ALERT:{severity.upper()}] {trigger_classes} on {node_id}"
            body = (
                f"Type: immediate\n"
                f"Severity: {severity}\n"
                f"Node: {node_id}\n"
                f"Trigger Classes: {trigger_classes_with_conf}\n"
                f"All Detected Classes: {all_classes}\n"
                f"Event TS: {event_ts}"
            )
            self._dispatch(subject=subject, body=body, json_payload=payload)

        self._flush_digest_if_due(now)

    def _queue_digest_item(self, dedup_key, node_id, class_name, confidence, event_ts):
        with self.lock:
            entry = self.digest_buffer.get(dedup_key)
            if entry is None:
                self.digest_buffer[dedup_key] = {
                    "node_id": node_id,
                    "class": class_name,
                    "count": 1,
                    "max_confidence": confidence,
                    "first_ts": event_ts,
                    "last_ts": event_ts,
                }
            else:
                entry["count"] += 1
                entry["max_confidence"] = max(entry["max_confidence"], confidence)
                entry["last_ts"] = event_ts

    def _flush_digest_if_due(self, now):
        with self.lock:
            if now - self.last_digest_sent < ALERT_DIGEST_WINDOW_SECONDS:
                return
            if not self.digest_buffer:
                self.last_digest_sent = now
                return
            digest_entries = list(self.digest_buffer.values())
            self.digest_buffer = {}
            self.last_digest_sent = now

        lines = []
        for entry in digest_entries:
            lines.append(
                f"Node={entry['node_id']} Class={entry['class']} Count={entry['count']} "
                f"MaxConf={entry['max_confidence']:.2f} FirstTS={entry['first_ts']} LastTS={entry['last_ts']}"
            )
        body = "Type: digest\n\n" + "\n".join(lines)
        payload = {
            "type": "digest",
            "items": digest_entries,
            "window_seconds": ALERT_DIGEST_WINDOW_SECONDS,
        }
        subject = f"[ALERT DIGEST] {len(digest_entries)} grouped detections"
        self._dispatch(subject=subject, body=body, json_payload=payload)

    def _dispatch(self, subject, body, json_payload):
        if self.dry_run:
            return

        if callable(self.on_alert):
            try:
                self.on_alert(subject, body, json_payload)
            except Exception as exc:
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
                    data={
                        "chat_id": self.telegram_chat_id,
                        "caption": caption[:1024],
                    },
                    files={"photo": ("alert_image.jpg", image_bytes, "image/jpeg")},
                    timeout=10,
                )
            else:
                response = requests.post(
                    f"{base_url}/sendMessage",
                    json={
                        "chat_id": self.telegram_chat_id,
                        "text": caption,
                    },
                    timeout=10,
                )

            if response.status_code != 200:
                logging.error(f"Telegram alert failed: {response.status_code} {response.text}")
        except Exception as exc:
            logging.error(f"Telegram alert failed: {exc}")

    def _send_webhook(self, payload):
        if not self.webhook_url:
            return

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if not (200 <= response.status_code < 300):
                logging.error(f"Webhook alert failed: {response.status_code} {response.text}")
        except Exception as exc:
            logging.error(f"Webhook alert failed: {exc}")