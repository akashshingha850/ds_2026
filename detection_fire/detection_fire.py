import base64
import json
import os
import socket
import threading
import time
import logging
from datetime import datetime, timedelta
import cv2
import numpy as np
import zmq
import sys
from ultralytics import YOLO
from utils import ZMQNode

# Add parent directory to path to import config
sys.path.append('.')

from config import (
    MOTION_IMAGE_PORT,
    DETECTION_FIRE_PORT,
    YOLO_FIRE_CONFIDENCE,
    DISCOVERY_PORT_DETECTION,
)


class DetectionProcessor(ZMQNode):
    def __init__(self, model_path):
        super().__init__('detection_fire', discovery_port=DISCOVERY_PORT_DETECTION)
        self.pub_port = DETECTION_FIRE_PORT
        self.model_path = model_path
        self.model = self.load_model()
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.setsockopt(zmq.RCVHWM, int(os.environ.get("SUB_RCV_HWM", "5000")))
        self.sub_socket.setsockopt(zmq.RCVBUF, int(os.environ.get("SUB_RCV_BUF", str(8 * 1024 * 1024))))
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.det_pub = self.context.socket(zmq.PUB)
        self.det_pub.setsockopt(zmq.SNDHWM, int(os.environ.get("DET_PUB_SND_HWM", "5000")))
        self.det_pub.bind(f"tcp://*:{DETECTION_FIRE_PORT}")


    def _compute_queue_age_seconds(self, send_ts, recv_ts_iso):
        if not send_ts or send_ts == "unknown" or not recv_ts_iso:
            return None
        try:
            recv_dt = datetime.fromisoformat(recv_ts_iso)
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

    def load_model(self):
        """Load the YOLO model from the given path."""
        return YOLO(self.model_path)

    def run_inference(self, image):
        """Run inference on the image using the model."""
        return self.model(image, conf=YOLO_FIRE_CONFIDENCE)

    def save_image(self, results, sender, timestamp):
        """Save YOLO-annotated result image to disk."""
        output_dir = "detection_images"
        os.makedirs(output_dir, exist_ok=True)
        safe_ts = timestamp.replace(":", "-")
        image_path = os.path.join(output_dir, f"{sender}_{safe_ts}.jpg")
        if not results:
            return
        annotated_image = results[0].plot()
        cv2.imwrite(image_path, annotated_image)
        logging.info(f"Saved result image: {image_path}")

    def publish_detection_results(self, detections, timestamp, sender, image_id=None):
        """Publish detection results via ZeroMQ."""
        message = {
            "type": "detection_results",
            "node_id": self.node_id,
            "sender": sender,
            "detections": detections,
            "ts": timestamp,
            "image_id": image_id,
        }
        self.det_pub.send_json(message)
        logging.info(f"{self.node_id} Published Image #{image_id} results: {detections}")

    def subscriber_loop(self):
        motion_host_fallback = os.environ.get("MOTION_HOST", "motion")
        while not self.stop_event.is_set():
            message = self.dynamic_peer_subscription(
                suffix='-motion',
                fallback_port=MOTION_IMAGE_PORT,
                fallback_host=motion_host_fallback,
                sub_socket=self.sub_socket,
                poll_timeout=1000,
                discovery_interval=30
            )
            if message is None:
                continue
            recv_ts = datetime.now().isoformat()
            if message.get("type") != "image":
                continue
            image_b64 = message.get("image_data")
            sender = message.get("node_id", "unknown")
            image_id = message.get("image_id", None)
            if not image_b64:
                continue
            decode_start = time.perf_counter()
            jpeg_bytes = base64.b64decode(image_b64)
            frame = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            decode_ms = (time.perf_counter() - decode_start) * 1000
            if frame is None:
                print("[SUB] Failed to decode image")
                continue
            inference_start = time.perf_counter()
            results = self.run_inference(frame)
            inference_ms = (time.perf_counter() - inference_start) * 1000
            detection_ts = datetime.now().isoformat()
            # print(f"[SUB] #{image_id} recieved from {sender}")
            # Prepare detection results
            detections = []
            for result in results:
                for box in result.boxes:
                    class_id = int(box.cls)
                    confidence = round(float(box.conf), 2)
                    class_name = self.model.names[class_id]
                    detections.append({
                        "class": class_name,
                        "confidence": confidence
                    })
            send_ts = message.get("ts", "unknown")
            queue_age_s = self._compute_queue_age_seconds(send_ts, recv_ts)
            queue_age_text = f"{queue_age_s:.3f}s" if queue_age_s is not None else "unknown"
            logging.info(
                f"{self.node_id} received image #{image_id} from {sender} - Send TS: {send_ts} - Recv TS: {recv_ts} - Detect TS: {detection_ts} "
                f"- Queue Age: {queue_age_text} - Decode: {decode_ms:.2f}ms - Inference: {inference_ms:.2f}ms - Results: {len(detections)} detections"
            )
            # Publish detection results
            publish_start = time.perf_counter()
            self.publish_detection_results(detections, detection_ts, sender, image_id=image_id)
            publish_ms = (time.perf_counter() - publish_start) * 1000
            # logging.info(f"{self.node_id} publish stage duration: {publish_ms:.2f}ms")
        self.sub_socket.close()

    def run(self):
        # Start discovery to find motion device
        self.start_discovery()

        # Start subscriber thread
        sub_thread = threading.Thread(target=self.subscriber_loop, daemon=True)
        sub_thread.start()

        logging.info(f"[DET_PUB:{self.node_id}] Listening on tcp://*:{DETECTION_FIRE_PORT}")
        logging.info(f"[SUB:{self.node_id}] Discovering motion devices...")
        logging.info(f"[PUB:{self.node_id}] Local IP: {self.get_local_ip()}")

        print(f"[DET:{self.node_id}] Detection processor started")
        print(f"[DET:{self.node_id}] Local IP: {self.get_local_ip()}\n")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("User stopped detection processor with Ctrl+C.")
        finally:
            self.det_pub.close()
            self.cleanup()

if __name__ == "__main__":
    # Hardcoded model path
    model_path = "detection_fire/yolo_fire_ncnn_model"

    processor = DetectionProcessor(model_path)
    processor.run()
