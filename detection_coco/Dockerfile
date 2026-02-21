FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Use service-local requirements file
COPY detection_coco/requirements.txt /app/requirements.txt
COPY shared/utils.py utils.py
COPY shared/config.py config.py
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY detection_coco/detection_coco.py /app/detection_coco.py

CMD ["python", "/app/detection_coco.py"]
