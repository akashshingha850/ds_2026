import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from alerting import AlertManager


EVENTS_FILE = "events.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("api_server.log"),
        logging.StreamHandler(),
    ],
)


def load_events():
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_events(events):
    with open(EVENTS_FILE, "w", encoding="utf-8") as file:
        json.dump(events, file, indent=2)


EVENTS = load_events()
ALERT_MANAGER = AlertManager()


class EventHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/data":
            self._send_json(200, EVENTS)
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/api/data":
            self._send_json(404, {"error": "Not found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"status": "error", "message": "Invalid JSON payload"})
            return

        EVENTS.append(payload)
        save_events(EVENTS)

        try:
            ALERT_MANAGER.process_event(payload)
        except Exception as exc:
            logging.error(f"Alert processing failed: {exc}")

        self._send_json(200, {"status": "success", "count": len(EVENTS)})

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8000
    print(f"API server running at http://{host}:{port}/api/data")
    server = ThreadingHTTPServer((host, port), EventHandler)
    server.serve_forever()