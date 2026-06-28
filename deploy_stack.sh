#!/usr/bin/env bash
set -euo pipefail


# Fill this in once, or export DOCKERHUB_USERNAME in your shell.
DOCKERHUB_USERNAME="akashshingha"
STACK_NAME="ds_2026"
COMPOSE_FILE="docker-compose.yml"
ALERT_ENV_FILE=".env"

# stop and remove existing stack if it exists
if docker stack ls | grep -q "${STACK_NAME}"; then
  echo "Removing existing stack ${STACK_NAME}..."
  docker stack rm "${STACK_NAME}"
  # Wait for the stack to be fully removed
  while docker stack ls | grep -q "${STACK_NAME}"; do
    echo "Waiting for stack ${STACK_NAME} to be removed..."
    sleep 5
  done
fi

if [[ -n "${DOCKERHUB_USERNAME:-}" && "${DOCKERHUB_USERNAME}" != "yourdockerhubusername" ]]; then
  export DOCKERHUB_USERNAME
elif [[ -n "${DOCKERHUB_USERNAME:-}" && "${DOCKERHUB_USERNAME}" == "yourdockerhubusername" ]]; then
  echo "Please set DOCKERHUB_USERNAME in deploy_stack.sh (or export it before running)."
  exit 1
fi

echo "Using Docker Hub username: ${DOCKERHUB_USERNAME}"

if [[ ! -f "${ALERT_ENV_FILE}" ]]; then
  if [[ -f ".env.example" ]]; then
    cp ".env.example" "${ALERT_ENV_FILE}"
    echo "Created ${ALERT_ENV_FILE} from template. Please edit it with real Telegram credentials."
  else
    echo "Warning: ${ALERT_ENV_FILE} not found. Alert Telegram env vars will use defaults."
  fi
fi

if [[ -f "${ALERT_ENV_FILE}" ]]; then
  set -a
  source "${ALERT_ENV_FILE}"
  set +a
fi

echo "[1/3] Building images..."
docker build -t "${DOCKERHUB_USERNAME}/ds-motion:latest" -f motion/Dockerfile .
# coco and fire share the single ds-detection image (DETECTOR env selects model)
# docker build -t "${DOCKERHUB_USERNAME}/ds-detection:latest" -f detection/Dockerfile .
# docker build -t "${DOCKERHUB_USERNAME}/ds-alert:latest" -f alert/Dockerfile .
# docker build -t "${DOCKERHUB_USERNAME}/ds-system-monitor:latest" -f system_monitor/Dockerfile .

echo "[2/3] Pushing images to Docker Hub..."
docker push "${DOCKERHUB_USERNAME}/ds-motion:latest"
# docker push "${DOCKERHUB_USERNAME}/ds-detection:latest"
# docker push "${DOCKERHUB_USERNAME}/ds-alert:latest"
# docker push "${DOCKERHUB_USERNAME}/ds-system-monitor:latest"

echo "[3/3] Deploying Docker stack..."
docker stack deploy --with-registry-auth -c docker-compose.yml ds_2026

echo "Done. Current services:"
docker stack services "${STACK_NAME}"
