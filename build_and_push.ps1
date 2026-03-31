# Build and push to registry.p4tkry.pl
# Usage: .\build_and_push.ps1 [VERSION] [TAG]

param(
    [string]$Version = "1.0",
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"

$Context = "desktop-linux"
$Registry = "registry.p4tkry.pl"
$Image = "$Registry/ai-one"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Docker Build & Push Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Build Context: $Context"
Write-Host "Registry: $Registry"
Write-Host "Image: $Image"
Write-Host "Version: $Version"
Write-Host "Tag: $Tag"
Write-Host ""

# Verify context exists
Write-Host "Checking docker contexts..." -ForegroundColor Yellow
$contexts = docker context ls --format "{{.Name}}"
if ($contexts -notcontains $Context) {
    Write-Host "❌ Context '$Context' not found" -ForegroundColor Red
    Write-Host "Available contexts:"
    docker context ls
    exit 1
}

# Switch to build context
Write-Host "🔧 Using context: $Context" -ForegroundColor Green
$env:DOCKER_CONTEXT = $Context

# Check if logged in to registry
Write-Host "Checking docker registry credentials..." -ForegroundColor Yellow
$dockerInfo = docker info 2>&1
if ($dockerInfo -notmatch "Registry") {
    Write-Host "⚠️  Not logged in to $Registry" -ForegroundColor Yellow
    Write-Host "Please login: docker --context $Context login $Registry"
    exit 1
}

# Build image
Write-Host "📦 Building image on $Context..." -ForegroundColor Green
docker build `
    --build-arg VERSION=$Version `
    -t "${Image}:$Tag" `
    -t "${Image}:$Version" `
    -t "${Image}:latest" `
    .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Build failed" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Build completed" -ForegroundColor Green

# Push to registry
Write-Host "🚀 Pushing to registry..." -ForegroundColor Green
docker push "${Image}:$Tag"
docker push "${Image}:$Version"
docker push "${Image}:latest"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Push failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "✓ Push completed successfully!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Image available at:"
Write-Host "  • ${Image}:$Tag"
Write-Host "  • ${Image}:$Version"
Write-Host "  • ${Image}:latest"
Write-Host ""
Write-Host "Deploy with:"
Write-Host "  .\deploy.ps1"
