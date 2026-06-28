FROM ros:humble-ros-base

ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1 \
	RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

WORKDIR /app

# pip, CycloneDDS RMW + message packages
RUN apt-get update && apt-get install -y --no-install-recommends \
	python3-pip \
	ros-humble-rmw-cyclonedds-cpp \
	ros-humble-std-msgs \
	&& rm -rf /var/lib/apt/lists/*

COPY system_monitor/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir -r /app/requirements.txt

# Shared modules + main script + config
COPY shared/ros_common.py /app/ros_common.py
COPY shared/config.py /app/config.py
COPY config.yaml /app/config.yaml
COPY system_monitor/system_monitor.py /app/system_monitor.py

# Source the ROS 2 environment, then run the node
CMD ["bash", "-lc", "source /opt/ros/humble/setup.bash && exec python3 /app/system_monitor.py"]
