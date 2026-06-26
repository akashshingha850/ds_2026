import json
import logging
import sys
import time
from datetime import datetime

import cv2
import ffmpeg
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String

# Allow importing the shared config / helpers copied into /app
sys.path.append('.')

from config import (
    MOTION_URL,
    MOTION_THRESHOLD,
    MOTION_FPS,
    PIXEL_DIFF_THRESHOLD,
    BLUR_SIGMA,
    KERNEL_SIZE,
    MOTION_IMAGE_PUBLISH_COOLDOWN,
    TOPIC_MOTION_FLAG,
    TOPIC_MOTION_IMAGE,
)
from ros_common import resolve_device_hostname, ros_namespace, setup_logging


def get_video_dimensions(url):
    """Probe the video stream and return width and height."""
    retry_delay = 1  # seconds
    attempt = 1
    while True:
        try:
            probe = ffmpeg.probe(url)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            width = int(video_info['width'])
            height = int(video_info['height'])
            if width <= 0 or height <= 0:
                return 0, 0  # Invalid dimensions, return 0,0 to indicate empty stream
            return width, height
        except (ffmpeg.Error, StopIteration) as e:
            print(f"Video dimension probe failed (attempt {attempt}): {e}")
            print(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            attempt += 1


class MotionDetector(Node):
    def __init__(self):
        super().__init__('motion', namespace=ros_namespace())
        self.node_id = f"{resolve_device_hostname()}-motion"

        # Reliable, keep-last QoS so detection / alert subscribers don't miss
        # the comparatively low-rate motion events.
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=50,
        )
        self.flag_pub = self.create_publisher(String, TOPIC_MOTION_FLAG, qos)
        self.image_pub = self.create_publisher(CompressedImage, TOPIC_MOTION_IMAGE, qos)

        self.prev_blurred_frame = None
        self.last_motion_state = 0
        self.image_id = 1  # Incremental image ID

    def gaussian_blur(self, image, kernel_size, sigma):
        return cv2.GaussianBlur(image, (kernel_size, kernel_size), sigma)

    def detect_motion(self, prev_frame, current_frame, pixel_diff_threshold):
        if prev_frame is None:
            return None

        diff = np.abs(current_frame - prev_frame)
        changed_pixels = (diff > pixel_diff_threshold).astype(np.float32)
        change_ratio = np.mean(changed_pixels)

        return change_ratio

    def publish_motion_flag(self, flag, timestamp):
        msg = String()
        msg.data = json.dumps({
            "type": "motion_flag",
            "node_id": self.node_id,
            "flag": flag,
            "ts": timestamp,
        })
        self.flag_pub.publish(msg)

    def publish_motion_image(self, frame, timestamp):
        t_start = time.time()
        success, encoded_img = cv2.imencode('.jpg', frame)
        if success:
            image_bytes = encoded_img.tobytes()
            image_size_kb = len(image_bytes) / 1024

            msg = CompressedImage()
            msg.format = "jpeg"
            msg.data = image_bytes
            # Carry the per-image metadata (node_id / image_id / ts) in the
            # header frame_id as JSON, matching the fields the alert service
            # uses to correlate motion images with detection results.
            msg.header.frame_id = json.dumps({
                "node_id": self.node_id,
                "image_id": self.image_id,
                "ts": timestamp,
            })
            self.image_pub.publish(msg)

            t_end = time.time()
            publish_latency_ms = (t_end - t_start) * 1000
            logging.info(
                f"{self.node_id} published image #{self.image_id} ({image_size_kb:.2f} KB) at {timestamp} "
                f"| publish latency: {publish_latency_ms:.3f} ms (start={t_start:.6f}, end={t_end:.6f})"
            )
            self.image_id += 1
        else:
            logging.error("Failed to encode image")

    def run(self):
        logging.info(f"[FLAG_PUB:{self.node_id}] Publishing on topic '{TOPIC_MOTION_FLAG}'")
        logging.info(f"[IMAGE_PUB:{self.node_id}] Publishing on topic '{TOPIC_MOTION_IMAGE}'")

        while rclpy.ok():
            width, height = get_video_dimensions(MOTION_URL)
            if width > 0 and height > 0:
                break
            print("Stream has invalid dimensions (0x0), waiting for valid stream...")
            time.sleep(1)

        process = (ffmpeg
            .input(MOTION_URL, rtsp_transport='udp')
            .filter('fps', fps=MOTION_FPS)  # Limit to MOTION_FPS FPS for processing
            .output('pipe:', format='rawvideo', pix_fmt='bgr24')
            .global_args('-loglevel', 'quiet')
            .run_async(pipe_stdout=True))

        bytes_per_frame = width * height * 3

        logging.info(f"{self.node_id} Starting motion detection... Press Ctrl+C to stop.")

        try:
            last_publish_time = 0
            publish_cooldown = MOTION_IMAGE_PUBLISH_COOLDOWN  # configured cooldown
            while rclpy.ok():
                in_bytes = process.stdout.read(bytes_per_frame)

                if len(in_bytes) != bytes_per_frame:
                    logging.warning("Incomplete frame received. Waiting 2 seconds and retrying...")
                    time.sleep(2)
                    continue

                frame = np.frombuffer(in_bytes, np.uint8).reshape((height, width, 3))

                if frame.size == 0:
                    print("Empty frame received, skipping...")
                    continue

                try:
                    t_start = time.time()

                    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                    blurred_frame = self.gaussian_blur(frame_gray, KERNEL_SIZE, BLUR_SIGMA)

                    change_ratio = self.detect_motion(self.prev_blurred_frame, blurred_frame, PIXEL_DIFF_THRESHOLD)

                    motion_detected = change_ratio is not None and change_ratio > MOTION_THRESHOLD

                    t_end = time.time()
                    detection_latency_ms = (t_end - t_start) * 1000
                    print(f"Detection latency: {detection_latency_ms:.3f} ms (start={t_start:.6f}, end={t_end:.6f})")

                    current_time = t_end

                    if motion_detected and self.last_motion_state == 0:
                        event_ts = datetime.now().time().isoformat()
                        self.publish_motion_flag(1, event_ts)
                        self.publish_motion_image(frame, event_ts)
                        last_publish_time = current_time
                    elif motion_detected and self.last_motion_state == 1:
                        # Cooldown logic for continuous motion
                        if current_time - last_publish_time >= publish_cooldown:
                            event_ts = datetime.now().time().isoformat()
                            # Optional: publish motion flag again if needed, else just image
                            self.publish_motion_image(frame, event_ts)
                            last_publish_time = current_time
                    elif not motion_detected and self.last_motion_state == 1:
                        event_ts = datetime.now().time().isoformat()
                        self.publish_motion_flag(0, event_ts)
                        print("Motion ended: sent flag 0")

                    self.prev_blurred_frame = blurred_frame
                    self.last_motion_state = 1 if motion_detected else 0

                    if change_ratio is not None and motion_detected:
                        print(f"Motion ratio: {change_ratio:.4f} - {'MOTION DETECTED' if motion_detected else 'No motion'}")
                except Exception as e:
                    logging.error(f"Error processing frame: {e}")
                    continue

        except KeyboardInterrupt:
            logging.info("User stopped motion detection with Ctrl+C.")
        finally:
            process.terminate()


def main():
    setup_logging()
    rclpy.init()
    detector = MotionDetector()
    try:
        detector.run()
    finally:
        detector.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
