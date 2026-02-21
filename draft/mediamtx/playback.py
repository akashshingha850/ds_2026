import subprocess
import sys

# Path to the video file to stream
test_video = "test.mp4"

# RTSP server address and path (adjust if needed)
rtsp_url = "rtsp://localhost:8554/playback"

# FFmpeg command to stream test.mp4 to the mediamtx server
ffmpeg_cmd = [
    "ffmpeg",
    "-re",  # Read input at native frame rate
    # "-stream_loop", "-1",  # Loop the video infinitely
    "-i", test_video,
    "-c:v", "copy",  # Copy video codec (or use libx264 for re-encode)
    "-c:a", "aac",   # Encode audio to AAC
    "-f", "rtsp",
    rtsp_url
]

try:
    print(f"Starting FFmpeg stream to {rtsp_url} from {test_video}...")
    subprocess.run(ffmpeg_cmd, check=True)
except subprocess.CalledProcessError as e:
    print(f"FFmpeg failed: {e}")
    sys.exit(1)
