# Fire Detection Processor

> **Note:** Migrated from ZeroMQ to **ROS 2 Humble**. It now runs as an `rclpy` node that subscribes to `motion/image` (`sensor_msgs/CompressedImage`) and publishes `detection_results` (`std_msgs/String` JSON) on topic `detection/fire`. The `ZMQNode` / port / peer-discovery details below are historical; transport is now DDS (CycloneDDS). See the repo `README.md` for the current topic map.

The fire detection processor runs YOLO inference on motion-triggered images and publishes fire-related detection results over ROS 2 topics.

## Overview

`DetectionProcessor` extends `ZMQNode` and:
1. Subscribes to motion image messages from peers with `-motion` suffix.
2. Decodes base64 JPEG frames.
3. Runs YOLO inference using fire-specific confidence settings.
4. Publishes structured detection results, preserving `image_id`.

## Dependencies

- `ultralytics`
- `opencv-python` (`cv2`)
- `pyzmq`
- `numpy`
- `base64`

## Configuration

From `config.py`:
- `MOTION_IMAGE_PORT`
- `DETECTION_FIRE_PORT`
- `YOLO_FIRE_CONFIDENCE`
- `DISCOVERY_PORT_DETECTION`

Environment variables:
- `SUB_RCV_HWM` (default `5000`)
- `SUB_RCV_BUF` (default `8 * 1024 * 1024`)
- `DET_PUB_SND_HWM` (default `5000`)
- `MOTION_HOST` (fallback host, default `motion`)

## Message Formats

### Input (from motion)
```json
{
	"type": "image",
	"node_id": "hostname-motion",
	"image_data": "base64_encoded_jpeg",
	"ts": "15:11:11.186105",
	"image_id": 12,
	"size": "80.35 KB"
}
```

### Output (detection results)
```json
{
	"type": "detection_results",
	"node_id": "hostname-detection_fire",
	"sender": "hostname-motion",
	"detections": [
		{
			"class": "fire",
			"confidence": 0.91
		}
	],
	"ts": "2026-02-24T15:11:11.186105",
	"image_id": 12
}
```

## Processing Flow

1. Receive image JSON from the motion publisher.
2. Decode `image_data` into an OpenCV frame.
3. Run YOLO inference with `YOLO_FIRE_CONFIDENCE`.
4. Extract detections as `{class, confidence}`.
5. Compute queue age from message `ts` and local receive timestamp.
6. Publish `detection_results` with `image_id`.

## Logging

The processor logs:
- Image source and `image_id`
- Send/receive/detect timestamps
- Queue age, decode time, inference time
- Number of detections and publish event

Example log lines:
```text
hostname-detection_fire received image #12 from hostname-motion - Send TS: 15:11:11.186105 - Recv TS: 2026-02-24T15:11:11.240000 - Detect TS: 2026-02-24T15:11:11.360000 - Queue Age: 0.054s - Decode: 7.10ms - Inference: 118.42ms - Results: 1 detections
Image #12 results published: [{'class': 'fire', 'confidence': 0.91}]
```

## Run

```bash
python detection_fire/detection_fire.py
```

Default model path in `__main__`:
```python
model_path = "detection_fire/yolo_fire_ncnn_model"
```

## Optional Annotated Image Saving

`save_image(results, sender, timestamp)` is implemented but not called by default.
If enabled, images are written to:

`detection_images/{sender}_{timestamp}.jpg`
