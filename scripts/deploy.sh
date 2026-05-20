#!/usr/bin/env bash
# End-to-end Minikube deployment for CricBuzz API.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

IMAGE_NAME="${IMAGE_NAME:-crickbuzz-api:latest}"
NAMESPACE="${NAMESPACE:-crickbuzz}"
MINIKUBE_PROFILE="${MINIKUBE_PROFILE:-minikube}"
SKIP_MINIKUBE_START="${SKIP_MINIKUBE_START:-0}"

log() { printf '\n==> %s\n' "$*"; }

step_minikube_start() {
  if [[ "${SKIP_MINIKUBE_START}" == "1" ]]; then
    log "Skipping Minikube start (SKIP_MINIKUBE_START=1)"
    return
  fi
  log "Starting Minikube profile '${MINIKUBE_PROFILE}'"
  minikube start -p "${MINIKUBE_PROFILE}"
  minikube addons enable storage-provisioner -p "${MINIKUBE_PROFILE}" || true
  minikube addons enable ingress -p "${MINIKUBE_PROFILE}" || true
}

step_docker_build() {
  log "Building Docker image '${IMAGE_NAME}' inside Minikube's Docker daemon"
  eval "$(minikube -p "${MINIKUBE_PROFILE}" docker-env)"
  docker build -t "${IMAGE_NAME}" .
}

step_k8s_apply() {
  log "Applying Kubernetes manifests (kustomize)"
  kubectl apply -k k8s/

  log "Waiting for PostgreSQL StatefulSet to be ready"
  kubectl -n "${NAMESPACE}" rollout status statefulset/postgres --timeout=600s
}

step_db_migrate() {
  log "Running database migrations (schema bootstrap Job)"
  kubectl -n "${NAMESPACE}" delete job crickbuzz-db-migrate --ignore-not-found=true
  kubectl apply -f k8s/db-migrate-job.yaml
  kubectl -n "${NAMESPACE}" wait --for=condition=complete job/crickbuzz-db-migrate --timeout=600s

  log "Migration job logs:"
  kubectl -n "${NAMESPACE}" logs job/crickbuzz-db-migrate --tail=50 || true
}

step_wait_api() {
  log "Waiting for API Deployment to become available"
  kubectl -n "${NAMESPACE}" rollout status deployment/crickbuzz-api --timeout=600s
}

step_print_url() {
  export NAMESPACE MINIKUBE_PROFILE
  bash scripts/print-urls.sh
}

main() {
  step_minikube_start
  step_docker_build
  step_k8s_apply
  step_db_migrate
  step_wait_api
  step_print_url
  log "Deployment complete."
}

main "$@"
