#!/usr/bin/env bash
# Print reachable API URLs after Minikube deployment.
set -euo pipefail

NAMESPACE="${NAMESPACE:-crickbuzz}"
MINIKUBE_PROFILE="${MINIKUBE_PROFILE:-minikube}"
NODEPORT="${NODEPORT:-30080}"

MINIKUBE_IP="$(minikube ip -p "${MINIKUBE_PROFILE}")"
NODEPORT_URL="http://${MINIKUBE_IP}:${NODEPORT}"
DOCS_URL="${NODEPORT_URL}/docs"
HEALTH_URL="${NODEPORT_URL}/health"

SERVICE_URL=""
if SERVICE_URL="$(minikube service crickbuzz-api-nodeport -n "${NAMESPACE}" -p "${MINIKUBE_PROFILE}" --url 2>/dev/null | head -n1)"; then
  :
fi

echo ""
echo "========================================"
echo " CricBuzz API is deployed on Minikube"
echo "========================================"
echo ""
echo "NodePort (direct):     ${NODEPORT_URL}"
echo "Swagger UI:            ${DOCS_URL}"
echo "Health check:          ${HEALTH_URL}"
if [[ -n "${SERVICE_URL}" ]]; then
  echo "minikube service URL:  ${SERVICE_URL}"
fi
echo ""
echo "Ingress (optional):    http://crickbuzz.local/docs"
echo "  Add to hosts file:   ${MINIKUBE_IP}  crickbuzz.local"
echo ""
echo "Useful commands:"
echo "  kubectl -n ${NAMESPACE} get pods"
echo "  kubectl -n ${NAMESPACE} logs -l app.kubernetes.io/component=api -f"
echo ""
