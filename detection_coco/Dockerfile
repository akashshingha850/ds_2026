FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Use service-local requirements file
COPY detection_coco/requirements.txt /app/requirements.txt
COPY shared/utils.py /app/utils.py
COPY shared/config.py /app/config.py


# Install OpenCV system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
	libglib2.0-0 libsm6 libxext6 libxrender-dev libxcb1 libgl1 \
	&& rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --upgrade pip && \
	pip install -r /app/requirements.txt

# Copy main script
COPY detection_coco/detection_coco.py /app/detection_coco.py

# Copy NCNN model directory (.bin, .param, metadata)
COPY detection_coco/yolo26n_ncnn_model/ /app/detection_coco/yolo26n_ncnn_model/

# (Optional) Clean up __pycache__
RUN find /app -type d -name '__pycache__' -exec rm -r {} + || true

CMD ["python", "/app/detection_coco.py"]
