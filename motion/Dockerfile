FROM ros:humble-ros-base

ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1 \
	RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

WORKDIR /app

# ffmpeg (provides ffprobe), pip, CycloneDDS RMW + message packages
RUN apt-get update && apt-get install -y --no-install-recommends \
	ffmpeg python3-pip \
	ros-humble-rmw-cyclonedds-cpp \
	ros-humble-sensor-msgs ros-humble-std-msgs \
	&& rm -rf /var/lib/apt/lists/*

# Install Python requirements first so edits to shared modules / source
# below don't invalidate the (slow) pip layer.
COPY motion/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir -r /app/requirements.txt

# Shared modules + service runtime file
COPY shared/ros_common.py /app/ros_common.py
COPY shared/config.py /app/config.py
COPY config.yaml /app/config.yaml
COPY motion/motion.py /app/motion.py

# Source the ROS 2 environment, then run the node
CMD ["bash", "-lc", "source /opt/ros/humble/setup.bash && exec python3 /app/motion.py"]
