FROM ros:humble-ros-base

ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1 \
	RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

WORKDIR /app

# OpenCV runtime libs, pip, CycloneDDS RMW + message packages
RUN apt-get update && apt-get install -y --no-install-recommends \
	python3-pip \
	libglib2.0-0 libsm6 libxext6 libxrender-dev libxcb1 libgl1 \
	ros-humble-rmw-cyclonedds-cpp \
	ros-humble-sensor-msgs ros-humble-std-msgs \
	&& rm -rf /var/lib/apt/lists/*

# Install Python requirements first so edits to shared modules / source
# below don't invalidate the (slow) torch/ultralytics pip layer.
COPY detection/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir -r /app/requirements.txt

# Shared modules + main script + config
COPY shared/ros_common.py /app/ros_common.py
COPY shared/config.py /app/config.py
COPY config.yaml /app/config.yaml
COPY detection/detection.py /app/detection.py

# Both detector models (coco, fire). The DETECTOR env var selects which one
# the container loads at runtime via MODEL_PATH (default models/<detector>).
COPY detection/models/ /app/models/

# (Optional) Clean up __pycache__
RUN find /app -type d -name '__pycache__' -exec rm -r {} + || true

# Source the ROS 2 environment, then run the node
CMD ["bash", "-lc", "source /opt/ros/humble/setup.bash && exec python3 /app/detection.py"]
