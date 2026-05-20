# CricBuzz — Minikube deployment automation
# Usage:
#   make deploy          # full pipeline
#   make deploy-ps       # same pipeline via PowerShell (Windows)
#   make teardown        # remove workloads (keeps Minikube running)

IMAGE_NAME    ?= crickbuzz-api:latest
NAMESPACE     ?= crickbuzz
MINIKUBE_PROFILE ?= minikube
NODEPORT      ?= 30080

.PHONY: help deploy deploy-ps minikube-start docker-build k8s-apply db-migrate wait-api url teardown logs status

help:
	@echo "Targets:"
	@echo "  deploy         - Start Minikube, build image, apply manifests, migrate DB, print URL"
	@echo "  deploy-ps      - Same as deploy using scripts/deploy.ps1 (Windows PowerShell)"
	@echo "  minikube-start - Start Minikube and enable addons"
	@echo "  docker-build   - Build API image in Minikube Docker"
	@echo "  k8s-apply      - kubectl apply -k k8s/ and wait for Postgres"
	@echo "  db-migrate     - Run schema bootstrap Job"
	@echo "  wait-api       - Wait for API Deployment rollout"
	@echo "  url            - Print API access URLs"
	@echo "  teardown       - Delete crickbuzz namespace resources"
	@echo "  logs           - Tail API pod logs"
	@echo "  status         - Show pods and services"

deploy: minikube-start docker-build k8s-apply db-migrate wait-api url
	@echo ""
	@echo "Deployment finished."

deploy-ps:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/deploy.ps1

minikube-start:
	@echo "==> Starting Minikube ($(MINIKUBE_PROFILE))"
	minikube start -p $(MINIKUBE_PROFILE)
	minikube addons enable storage-provisioner -p $(MINIKUBE_PROFILE) || true
	minikube addons enable ingress -p $(MINIKUBE_PROFILE) || true

docker-build:
	@echo "==> Building $(IMAGE_NAME) in Minikube Docker"
	eval $$(minikube -p $(MINIKUBE_PROFILE) docker-env) && docker build -t $(IMAGE_NAME) .

k8s-apply:
	@echo "==> Applying Kubernetes manifests"
	kubectl apply -k k8s/
	kubectl -n $(NAMESPACE) rollout status statefulset/postgres --timeout=600s

db-migrate:
	@echo "==> Running database migrations"
	kubectl -n $(NAMESPACE) delete job crickbuzz-db-migrate --ignore-not-found=true
	kubectl apply -f k8s/db-migrate-job.yaml
	kubectl -n $(NAMESPACE) wait --for=condition=complete job/crickbuzz-db-migrate --timeout=600s
	kubectl -n $(NAMESPACE) logs job/crickbuzz-db-migrate --tail=50 || true

wait-api:
	@echo "==> Waiting for API deployment"
	kubectl -n $(NAMESPACE) rollout status deployment/crickbuzz-api --timeout=600s

url:
	@NAMESPACE=$(NAMESPACE) MINIKUBE_PROFILE=$(MINIKUBE_PROFILE) NODEPORT=$(NODEPORT) bash scripts/print-urls.sh

teardown:
	@echo "==> Removing namespace $(NAMESPACE)"
	kubectl delete namespace $(NAMESPACE) --ignore-not-found=true

logs:
	kubectl -n $(NAMESPACE) logs -l app.kubernetes.io/component=api -f --tail=100

status:
	@echo "==> Pods"
	kubectl -n $(NAMESPACE) get pods -o wide
	@echo ""
	@echo "==> Services"
	kubectl -n $(NAMESPACE) get svc
