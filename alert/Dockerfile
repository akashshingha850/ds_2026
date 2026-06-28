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

# Python dependencies needed by alert/alert.py
RUN pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir requests numpy opencv-python-headless pyyaml

# Copy alert service script + shared modules
COPY alert/alert.py /app/alert.py
COPY shared/ros_common.py /app/ros_common.py
COPY shared/config.py /app/config.py
COPY config.yaml /app/config.yaml

# Source the ROS 2 environment, then run the node
CMD ["bash", "-lc", "source /opt/ros/humble/setup.bash && exec python3 /app/alert.py"]
