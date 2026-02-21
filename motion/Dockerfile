FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1


WORKDIR /app

# Use service-local requirements file
COPY motion/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy project files
COPY . /app

CMD ["python", "motion/motion.py"]
