import json
import logging
import os
import threading

from flask import Flask, jsonify, request


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
EVENTS_LOCK = threading.Lock()
APP = Flask(__name__)


@APP.get("/api/data")
def get_data():
    with EVENTS_LOCK:
        snapshot = list(EVENTS)
    return jsonify(snapshot), 200


@APP.post("/api/data")
def post_data():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

    with EVENTS_LOCK:
        EVENTS.append(payload)
        save_events(EVENTS)
        events_count = len(EVENTS)

    return jsonify({"status": "success", "count": events_count}), 200


@APP.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Not found"}), 404


@APP.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 5000
    print(f"API server running at http://{host}:{port}/api/data")
    APP.run(host=host, port=port, threaded=True)