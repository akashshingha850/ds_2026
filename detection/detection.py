import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
from ultralytics import YOLO

# Allow importing the shared config / helpers copied into /app
sys.path.append('.')

import config
from config import TOPIC_MOTION_IMAGE
from ros_common import resolve_device_hostname, ros_namespace, setup_logging


# This single node serves every detector (coco, fire, ...). The DETECTOR env var
# selects which model to load, which output topic to publish on, and which
# confidence threshold to use. The config.yaml stays the single source for the
# per-detector topic names and confidence thresholds.
DETECTOR = os.getenv("DETECTOR", "coco").strip().lower()
MODEL_PATH = os.getenv("MODEL_PATH", f"models/{DETECTOR}")
TOPIC_DETECTION_OUT = getattr(config, f"TOPIC_DETECTION_{DETECTOR.upper()}")
DETECTION_CONFIDENCE = getattr(config, f"YOLO_{DETECTOR.upper()}_CONFIDENCE")


class DetectionProcessor(Node):
    def __init__(self, model_path):
        super().__init__(f'detection_{DETECTOR}', namespace=ros_namespace())
        self.node_id = f"{resolve_device_hostname()}-detection_{DETECTOR}"
        self.model_path = model_path
        self.model = self.load_model()

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=50,
        )
        self.det_pub = self.create_publisher(String, TOPIC_DETECTION_OUT, qos)
        self.sub = self.create_subscription(
            CompressedImage, TOPIC_MOTION_IMAGE, self.on_image, qos
        )

        logging.info(f"[DET_PUB:{self.node_id}] Publishing on topic '{TOPIC_DETECTION_OUT}'")
        logging.info(f"[SUB:{self.node_id}] Subscribing to motion images on '{TOPIC_MOTION_IMAGE}'")

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
        return self.model(image, conf=DETECTION_CONFIDENCE)

    def publish_detection_results(self, detections, timestamp, sender, image_id=None):
        """Publish detection results on the ROS 2 detection topic."""
        msg = String()
        msg.data = json.dumps({
            "type": "detection_results",
            "node_id": self.node_id,
            "sender": sender,
            "detections": detections,
            "ts": timestamp,
            "image_id": image_id,
        })
        self.det_pub.publish(msg)
        logging.info(f"{self.node_id} Published Image #{image_id} results: {detections}")

    def on_image(self, msg):
        recv_ts = datetime.now().isoformat()

        # Per-image metadata (node_id / image_id / ts) is carried in the
        # CompressedImage header frame_id as JSON by the motion node.
        try:
            meta = json.loads(msg.header.frame_id) if msg.header.frame_id else {}
        except (ValueError, TypeError):
            meta = {}
        sender = meta.get("node_id", "unknown")
        image_id = meta.get("image_id")
        send_ts = meta.get("ts", "unknown")

        decode_start = time.perf_counter()
        frame = cv2.imdecode(np.frombuffer(bytes(msg.data), dtype=np.uint8), cv2.IMREAD_COLOR)
        decode_ms = (time.perf_counter() - decode_start) * 1000
        if frame is None:
            print("[SUB] Failed to decode image")
            return

        inference_start = time.perf_counter()
        results = self.run_inference(frame)
        inference_ms = (time.perf_counter() - inference_start) * 1000
        detection_ts = datetime.now().isoformat()
        print(f"[SUB] received from {sender} (Image #{image_id})")

        detections = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls)
                confidence = round(float(box.conf), 2)
                class_name = self.model.names[class_id]
                detections.append({
                    "class": class_name,
                    "confidence": confidence,
                })

        queue_age_s = self._compute_queue_age_seconds(send_ts, recv_ts)
        queue_age_text = f"{queue_age_s:.3f}s" if queue_age_s is not None else "unknown"
        logging.info(
            f"{self.node_id} received image #{image_id} from {sender} - Send TS: {send_ts} - Recv TS: {recv_ts} - Detect TS: {detection_ts} "
            f"- Queue Age: {queue_age_text} - Decode: {decode_ms:.2f}ms - Inference: {inference_ms:.2f}ms - Results: {len(detections)} detections"
        )
        self.publish_detection_results(detections, detection_ts, sender, image_id=image_id)


def main():
    setup_logging()

    rclpy.init()
    processor = DetectionProcessor(MODEL_PATH)
    print(f"[DET:{processor.node_id}] Detection processor started (detector={DETECTOR}, model={MODEL_PATH})\n")
    try:
        rclpy.spin(processor)
    except KeyboardInterrupt:
        logging.info("User stopped detection processor with Ctrl+C.")
    finally:
        processor.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
