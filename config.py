# =============================================================================
# CONFIGURATION FILE FOR DISTRIBUTED SYSTEM
# =============================================================================

# -----------------------------------------------------------------------------
# PEER DISCOVERY (Shared UDP Broadcast Settings)
# -----------------------------------------------------------------------------
DISCOVERY_BROADCAST = "255.255.255.255"
NODE_PORT = 5555  # All nodes listen on this ZeroMQ port
DISCOVERY_INTERVAL = 2  # seconds between broadcast pings
DISCOVERY_PORT = 50000  # Default discovery port (fallback)


# -----------------------------------------------------------------------------
# MOTION DETECTION
# -----------------------------------------------------------------------------
MOTION_FLAG_PORT = 5556
MOTION_IMAGE_PORT = 5557
# MOTION_URL = 'rtsp://192.168.144.25:8554/main.264'  # SIYI Camera RTSP URL
MOTION_URL = 'rtsp://127.0.0.1:8554/stream' # Localhost RTSP URL for testing on MacBook
MOTION_URL = 'rtsp://172.20.10.2:31555/nvstream/opt/store/nvstreamer_videos/ccfootage.mp4' # Local RTSP URL for testing on Jetson Nano with local video file


MOTION_THRESHOLD = 0.33
PIXEL_DIFF_THRESHOLD = 50
BLUR_SIGMA = 1.5
KERNEL_SIZE = 5
MOTION_FPS = 10
DISCOVERY_PORT_MOTION = 50000  # Shared with detection for cross-device discovery

# -----------------------------------------------------------------------------
# DETECTION (YOLO)
# -----------------------------------------------------------------------------
DETECTION_COCO_PORT = 5558
YOLO_COCO_PATH = "detection_models/yolo26n_ncnn_model"  # NCNN model path
YOLO_COCO_CONFIDENCE = 0.5  # Confidence threshold for YOLO COCO

DETECTION_WPN_PORT = 5559
YOLO_WPN_PATH = "detection_models/yolo_weapon_ncnn_model"  # WPN model path
YOLO_WPN_CONFIDENCE = 0.5  # Confidence threshold for YOLO WPN

DETECTION_FIRE_PORT = 5560
YOLO_FIRE_PATH = "detection_models/yolo_fire_ncnn_model"  # FIRE model path
YOLO_FIRE_CONFIDENCE = 0.5  # Confidence threshold for YOLO FIRE

DISCOVERY_PORT_DETECTION = 50000  # Dedicated discovery port for detection nodes

# -----------------------------------------------------------------------------
# SYSTEM MONITOR
# -----------------------------------------------------------------------------
SYSTEM_MONITOR_INTERVAL = 1  # seconds
SYSTEM_MONITOR_PORT = 5599
# SYSTEM_MONITOR_IP = "localhost"  # For server.py connection (if needed)
DISCOVERY_PORT_SYSTEM = 50001  # Dedicated discovery port for system_monitor nodes


# -----------------------------------------------------------------------------
# RECORDING
# -----------------------------------------------------------------------------
RECORD_DURATION = 15  # seconds
RECORD_FPS = 10
