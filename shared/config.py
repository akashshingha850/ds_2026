# =============================================================================
# CONFIGURATION FILE FOR DISTRIBUTED SYSTEM
# =============================================================================
##
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
#MOTION_URL = 'rtsp://192.168.144.25:8554/main.264'  # SIYI Camera RTSP URL
# MOTION_URL = 'rtsp://127.0.0.1:8554/stream' #  RTSP URL for MediaMTX testing
MOTION_URL = 'rtsp://192.168.144.203:8554/playback'
#MOTION_URL = 'rtsp://172.20.10.2:31555/nvstream/opt/store/nvstreamer_videos/ccfootage.mp4' # Local RTSP URL for testing on Jetson Nano with local video file


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
YOLO_COCO_CONFIDENCE = 0.5  # Confidence threshold for YOLO COCO

# DETECTION_WPN_PORT = 5559
# YOLO_WPN_PATH = "detection_models/yolo_weapon_ncnn_model"  # WPN model path
# YOLO_WPN_CONFIDENCE = 0.5  # Confidence threshold for YOLO WPN

DETECTION_FIRE_PORT = 5559
YOLO_FIRE_CONFIDENCE = 0.5  # Confidence threshold for YOLO FIRE

DISCOVERY_PORT_DETECTION = 50000  # Dedicated discovery port for detection nodes

# -----------------------------------------------------------------------------
# SYSTEM MONITOR
# -----------------------------------------------------------------------------
SYSTEM_MONITOR_INTERVAL = 1  # seconds
SYSTEM_MONITOR_PORT = 5560
# SYSTEM_MONITOR_IP = "localhost"  # For server.py connection (if needed)
DISCOVERY_PORT_SYSTEM = 50001  # Dedicated discovery port for system_monitor nodes


# -----------------------------------------------------------------------------
# RECORDING
# -----------------------------------------------------------------------------
RECORD_DURATION = 15  # seconds
RECORD_FPS = 10



# -----------------------------------------------------------------------------
# ALERTING (API SERVER)
# -----------------------------------------------------------------------------
ALERTS_ENABLED = True
SERVER_PORT = 5000

# Trigger and filtering
ALERT_REQUIRE_MOTION_FLAG = True
ALERT_REQUIRE_DETECTIONS = True
ALERT_MIN_CONFIDENCE = 0.5
ALERT_CLASS_WHITELIST = []  # Empty means all classes

# Anti-spam
ALERT_COOLDOWN_SECONDS = 60
ALERT_DIGEST_WINDOW_SECONDS = 60
ALERT_NEW_OBJECT_ONLY = True
ALERT_OBJECT_INACTIVE_SECONDS = 30  # Consider class "new" again only after this many seconds unseen

# Hybrid strategy: immediate for critical classes, digest for others
ALERT_IMMEDIATE_CLASSES = ["weapon", "fire"]
ALERT_FIRST_HIT_IMMEDIATE = True  # Send first accepted detection immediately for any class
ALERT_EXCLUDED_NODE_PREFIXES = ["smtp-", "live-email-test"]  # Prevent test/synthetic node IDs from sending alerts

# Telegram bot settings
ALERT_TELEGRAM_ENABLED = True
ALERT_TELEGRAM_BOT_TOKEN = ""
ALERT_TELEGRAM_CHAT_ID = "6057187917"
ALERT_TELEGRAM_ATTACH_IMAGE = True

# Webhook settings
ALERT_WEBHOOK_ENABLED = False
ALERT_WEBHOOK_URL = ""

# Test mode: evaluates alert logic and logs what would be sent without network delivery
ALERT_DRY_RUN = False
