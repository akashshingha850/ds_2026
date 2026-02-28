import base64
import logging
import os
import threading
import time

import cv2
import numpy as np
import requests

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
)


class AlertManager:
    def __init__(self, on_alert=None):
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
        if not self._was_sent_recently(node_id, triggered_classes, now):
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
