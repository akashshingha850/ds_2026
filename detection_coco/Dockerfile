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
COPY detection_coco/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir -r /app/requirements.txt

# Shared modules + main script
COPY shared/ros_common.py /app/ros_common.py
COPY shared/config.py /app/config.py
COPY detection_coco/detection_coco.py /app/detection_coco.py

# Copy NCNN model directory (.bin, .param, metadata)
COPY detection_coco/yolo26n_ncnn_model/ /app/detection_coco/yolo26n_ncnn_model/

# (Optional) Clean up __pycache__
RUN find /app -type d -name '__pycache__' -exec rm -r {} + || true

# Source the ROS 2 environment, then run the node
CMD ["bash", "-lc", "source /opt/ros/humble/setup.bash && exec python3 /app/detection_coco.py"]
