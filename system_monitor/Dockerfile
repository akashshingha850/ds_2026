FROM python:3.10-alpine
WORKDIR /app
COPY system_monitor/requirements.txt .
RUN pip install -r requirements.txt
COPY system_monitor/system_monitor.py .
COPY shared/utils.py utils.py
COPY shared/config.py config.py
# Remove pip cache for smaller image
RUN rm -rf /root/.cache
CMD ["python", "system_monitor.py"]
