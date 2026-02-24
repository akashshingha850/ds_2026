# COCO Detection Processor

The COCO detection processor performs object detection on motion-triggered images using YOLO and publishes structured detection results over ZeroMQ.

## Overview

`DetectionProcessor` extends `ZMQNode` and does the following:
1. Dynamically subscribes to `-motion` peers for incoming images.
2. Decodes base64 JPEG payloads.
3. Runs YOLO inference with configured confidence threshold.
4. Publishes detection results with the original `image_id`.

## Dependencies

- `ultralytics`
- `opencv-python` (`cv2`)
- `pyzmq`
- `numpy`
- `base64`

## Configuration

Used values from `config.py`:
- `MOTION_IMAGE_PORT`
- `DETECTION_COCO_PORT`
- `YOLO_COCO_CONFIDENCE`
- `DISCOVERY_PORT_DETECTION`

Runtime tuning via environment variables:
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
    "node_id": "hostname-detection_coco",
    "sender": "hostname-motion",
    "detections": [
        {
            "class": "person",
            "confidence": 0.85
        }
    ],
    "ts": "2026-02-24T15:11:11.186105",
    "image_id": 12
}
```

## Processing Flow

1. Receive image message from motion publisher.
2. Decode base64 JPEG to OpenCV frame.
3. Run YOLO inference (`YOLO_COCO_CONFIDENCE`).
4. Extract `{class, confidence}` from detections.
5. Compute queue age from motion `ts` and local receive time.
6. Publish result payload including `image_id`.

## Logging

The processor logs:
- Incoming image source and `image_id`.
- Send/receive/detect timestamps.
- Queue age, decode time, inference time.
- Number of detections and publish event.

Example runtime lines:
```text
[SUB] received from hostname-motion (Image #12)
hostname-detection_coco received image #12 from hostname-motion - Send TS: 15:11:11.186105 - Recv TS: 2026-02-24T15:11:11.240000 - Detect TS: 2026-02-24T15:11:11.360000 - Queue Age: 0.054s - Decode: 7.10ms - Inference: 118.42ms - Results: 2 detections
Image #12 results published: [{'class': 'person', 'confidence': 0.85}]
```

## Run

```bash
python detection_coco/detection_coco.py
```

Model path used by default in `__main__`:
```python
model_path = "detection_coco/yolo26n_ncnn_model"
```

## Optional Image Saving

`save_image(results, sender, timestamp)` exists but is not called by default.
If enabled, files are written to `detection_images/{sender}_{timestamp}.jpg`.