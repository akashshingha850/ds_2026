# =============================================================================
# CONFIGURATION FILE FOR DISTRIBUTED SYSTEM
# =============================================================================

# -----------------------------------------------------------------------------
# PEER DISCOVERY (Shared UDP Broadcast Settings)
# -----------------------------------------------------------------------------
DISCOVERY_BROADCAST = "255.255.255.255"
DISCOVERY_INTERVAL = 2  # seconds between broadcast pings
DISCOVERY_PORT = 50000  # Default discovery port (fallback)

# -----------------------------------------------------------------------------
# SYSTEM MONITOR
# -----------------------------------------------------------------------------
SYSTEM_MONITOR_INTERVAL = 1  # seconds
SYSTEM_MONITOR_PORT = 5559
# SYSTEM_MONITOR_IP = "localhost"  # For server.py connection (if needed)
DISCOVERY_PORT_SYSTEM = 50000  # Dedicated discovery port for system_monitor nodes

# -----------------------------------------------------------------------------
# MOTION DETECTION
# -----------------------------------------------------------------------------
MOTION_FLAG_PORT = 5556
MOTION_IMAGE_PORT = 5557
MOTION_URL = 'rtsp://192.168.144.25:8554/main.264'  # 'rtsp://127.0.0.1:8554/stream'
MOTION_THRESHOLD = 0.33
PIXEL_DIFF_THRESHOLD = 50
BLUR_SIGMA = 1.5
KERNEL_SIZE = 5
MOTION_FPS = 10
DISCOVERY_PORT_MOTION = 50001  # Shared with detection for cross-device discovery

# -----------------------------------------------------------------------------
# DETECTION (YOLO)
# -----------------------------------------------------------------------------
DETECTION_PORT = 5558
YOLO_COCO_PATH = "detection_models/yolo26n_ncnn_model"  # NCNN model path
YOLO_COCO_CONFIDENCE = 0.5  # Confidence threshold for YOLO COCO
YOLO_WPN_PATH = "best_ncnn_model"  # WPN model path
DISCOVERY_PORT_DETECTION = 50002  # Dedicated discovery port for detection nodes

# -----------------------------------------------------------------------------
# RECORDING
# -----------------------------------------------------------------------------
RECORD_DURATION = 15  # seconds
RECORD_FPS = 10

# -----------------------------------------------------------------------------
# GENERAL (Shared Across Nodes)
# -----------------------------------------------------------------------------
NODE_PORT = 5555  # All nodes listen on this ZeroMQ port
