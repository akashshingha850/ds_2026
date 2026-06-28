#!/usr/bin/env bash
set -euo pipefail


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

# Load .env first so DOCKERHUB_USERNAME (and the alert secrets) are available.
if [[ ! -f "${ALERT_ENV_FILE}" ]]; then
  if [[ -f ".env.example" ]]; then
    cp ".env.example" "${ALERT_ENV_FILE}"
    echo "Created ${ALERT_ENV_FILE} from template. Please edit it with real values."
  else
    echo "Warning: ${ALERT_ENV_FILE} not found. Using defaults (local build)."
  fi
fi

if [[ -f "${ALERT_ENV_FILE}" ]]; then
  set -a
  source "${ALERT_ENV_FILE}"
  set +a
fi

# Docker Hub username comes from .env (or an exported env var). If unset, images
# are built locally. When set, they are only pushed if you are logged in.
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-}"

# Returns 0 if the Docker CLI is authenticated to Docker Hub.
docker_logged_in() {
  docker info 2>/dev/null | grep -q "Username:" && return 0
  # Fallback: a non-empty auth entry for Docker Hub in the CLI config.
  [[ -f "${HOME}/.docker/config.json" ]] && \
    grep -q '"auth"' "${HOME}/.docker/config.json" 2>/dev/null
}

# Decide whether to push. Use a real Docker Hub username only if one is set
# (and not the placeholder) AND we are logged in; otherwise build locally.
PUSH_IMAGES=true
if [[ -z "${DOCKERHUB_USERNAME}" || "${DOCKERHUB_USERNAME}" == "yourdockerhubusername" ]]; then
  echo "No Docker Hub username set — building locally (no push)."
  DOCKERHUB_USERNAME="local"
  PUSH_IMAGES=false
elif ! docker_logged_in; then
  echo "Not logged in to Docker Hub (run 'docker login') — building locally (no push)."
  DOCKERHUB_USERNAME="local"
  PUSH_IMAGES=false
fi
export DOCKERHUB_USERNAME

echo "Using image namespace: ${DOCKERHUB_USERNAME} (push=${PUSH_IMAGES})"

echo "[1/3] Building images..."
docker build -t "${DOCKERHUB_USERNAME}/ds-motion:latest" -f motion/Dockerfile .
# coco and fire share the single ds-detection image (DETECTOR env selects model)
# docker build -t "${DOCKERHUB_USERNAME}/ds-detection:latest" -f detection/Dockerfile .
# docker build -t "${DOCKERHUB_USERNAME}/ds-alert:latest" -f alert/Dockerfile .
# docker build -t "${DOCKERHUB_USERNAME}/ds-system-monitor:latest" -f system_monitor/Dockerfile .

if [[ "${PUSH_IMAGES}" == "true" ]]; then
  echo "[2/3] Pushing images to Docker Hub..."
  docker push "${DOCKERHUB_USERNAME}/ds-motion:latest"
  # docker push "${DOCKERHUB_USERNAME}/ds-detection:latest"
  # docker push "${DOCKERHUB_USERNAME}/ds-alert:latest"
  # docker push "${DOCKERHUB_USERNAME}/ds-system-monitor:latest"
else
  echo "[2/3] Skipping push (local build). Images are tagged ${DOCKERHUB_USERNAME}/ds-*:latest."
fi

echo "[3/3] Deploying Docker stack..."
docker stack deploy --with-registry-auth -c docker-compose.yml ds_2026

echo "Done. Current services:"
docker stack services "${STACK_NAME}"
