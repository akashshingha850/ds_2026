FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Use service-local requirements file
COPY detection_coco/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

CMD ["python", "detection_coco/detection_coco.py"]
