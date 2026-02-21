FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Use service-local requirements file
COPY detection_coco/requirements.txt /app/requirements.txt
COPY shared/utils.py /app/utils.py
COPY shared/config.py /app/config.py

# Install dependencies
RUN pip install --upgrade pip && \
	pip install --no-cache-dir -r /app/requirements.txt && \
	rm -rf /root/.cache /root/.config

# Copy main script
COPY detection_coco/detection_coco.py /app/detection_coco.py

# Copy only the required model file
COPY detection_coco/yolo26n_ncnn_model/model.ncnn.bin /app/detection_coco/yolo26n_ncnn_model/model.ncnn.bin

# (Optional) Clean up __pycache__
RUN find /app -type d -name '__pycache__' -exec rm -r {} + || true

CMD ["python", "/app/detection_coco.py"]
