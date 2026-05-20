# End-to-end Minikube deployment for CricBuzz API (Windows PowerShell).
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootDir

$ImageName = if ($env:IMAGE_NAME) { $env:IMAGE_NAME } else { "crickbuzz-api:latest" }
$Namespace = if ($env:NAMESPACE) { $env:NAMESPACE } else { "crickbuzz" }
$MinikubeProfile = if ($env:MINIKUBE_PROFILE) { $env:MINIKUBE_PROFILE } else { "minikube" }
$SkipMinikubeStart = if ($env:SKIP_MINIKUBE_START) { $env:SKIP_MINIKUBE_START } else { "0" }

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Start-MinikubeStep {
    if ($SkipMinikubeStart -eq "1") {
        Write-Step "Skipping Minikube start (SKIP_MINIKUBE_START=1)"
        return
    }
    Write-Step "Starting Minikube profile '$MinikubeProfile'"
    minikube start -p $MinikubeProfile
    minikube addons enable storage-provisioner -p $MinikubeProfile 2>$null
    minikube addons enable ingress -p $MinikubeProfile 2>$null
}

function Build-DockerImageStep {
    Write-Step "Building Docker image '$ImageName' inside Minikube's Docker daemon"
    & minikube -p $MinikubeProfile docker-env --shell powershell | Invoke-Expression
    docker build -t $ImageName .
}

function Apply-KubernetesStep {
    Write-Step "Applying Kubernetes manifests (kustomize)"
    kubectl apply -k k8s/

    Write-Step "Waiting for PostgreSQL StatefulSet to be ready"
    kubectl -n $Namespace rollout status statefulset/postgres --timeout=600s
}

function Invoke-DbMigrateStep {
    Write-Step "Running database migrations (schema bootstrap Job)"
    kubectl -n $Namespace delete job crickbuzz-db-migrate --ignore-not-found=true
    kubectl apply -f k8s/db-migrate-job.yaml
    kubectl -n $Namespace wait --for=condition=complete job/crickbuzz-db-migrate --timeout=600s

    Write-Step "Migration job logs"
    kubectl -n $Namespace logs job/crickbuzz-db-migrate --tail=50
}

function Wait-ApiStep {
    Write-Step "Waiting for API Deployment to become available"
    kubectl -n $Namespace rollout status deployment/crickbuzz-api --timeout=600s
}

function Show-UrlsStep {
    $NodePort = if ($env:NODEPORT) { $env:NODEPORT } else { "30080" }
    $MinikubeIp = (minikube ip -p $MinikubeProfile).Trim()
    $NodePortUrl = "http://${MinikubeIp}:${NodePort}"
    $DocsUrl = "${NodePortUrl}/docs"
    $HealthUrl = "${NodePortUrl}/health"

    $ServiceUrl = ""
    try {
        $ServiceUrl = (minikube service crickbuzz-api-nodeport -n $Namespace -p $MinikubeProfile --url 2>$null | Select-Object -First 1)
    } catch { }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host " CricBuzz API is deployed on Minikube" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "NodePort (direct):     $NodePortUrl"
    Write-Host "Swagger UI:            $DocsUrl"
    Write-Host "Health check:          $HealthUrl"
    if ($ServiceUrl) {
        Write-Host "minikube service URL:  $ServiceUrl"
    }
    Write-Host ""
    Write-Host "Ingress (optional):    http://crickbuzz.local/docs"
    Write-Host "  Add to hosts file:   $MinikubeIp  crickbuzz.local"
    Write-Host ""
    Write-Host "Useful commands:"
    Write-Host "  kubectl -n $Namespace get pods"
    Write-Host "  kubectl -n $Namespace logs -l app.kubernetes.io/component=api -f"
    Write-Host ""
}

Write-Step "CricBuzz Minikube deployment"
Start-MinikubeStep
Build-DockerImageStep
Apply-KubernetesStep
Invoke-DbMigrateStep
Wait-ApiStep
Show-UrlsStep
Write-Step "Deployment complete."
