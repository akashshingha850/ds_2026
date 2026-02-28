FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1
ENV ALERT_TELEGRAM_ENABLED=true \
	ALERT_TELEGRAM_BOT_TOKEN="" \
	ALERT_TELEGRAM_CHAT_ID="" \
	ALERT_TELEGRAM_ATTACH_IMAGE=true

WORKDIR /app

# Install OpenCV runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
	libglib2.0-0 libsm6 libxext6 libxrender-dev libxcb1 libgl1 \
	&& rm -rf /var/lib/apt/lists/*

# Install Python dependencies needed by alert/api_subscriber.py + alert/alerting.py
RUN pip install --upgrade pip && \
	pip install requests pyzmq numpy opencv-python-headless

# Copy alert service scripts
COPY alert/api_subscriber.py /app/api_subscriber.py
COPY alert/alerting.py /app/alerting.py
COPY shared/utils.py /app/utils.py

# Copy shared config expected as local module import: from config import ...
COPY shared/config.py /app/config.py

CMD ["python", "/app/api_subscriber.py"]
