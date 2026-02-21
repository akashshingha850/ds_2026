FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1


WORKDIR /app

# Use service-local requirements file
COPY motion/requirements.txt /app/requirements.txt
COPY shared/utils.py utils.py
COPY shared/config.py config.py
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy only service runtime file
COPY motion/motion.py /app/motion.py

CMD ["python", "/app/motion.py"]
