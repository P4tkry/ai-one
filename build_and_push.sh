#!/bin/bash

# Build and push to registry.p4tkry.pl
# Usage: ./build_and_push.sh [VERSION] [TAG]

set -e

VERSION=${1:-1.0}
TAG=${2:-latest}
CONTEXT="desktop-linux"
REGISTRY="registry.p4tkry.pl"
IMAGE="$REGISTRY/ai-one"

echo "================================"
echo "Docker Build & Push Script"
echo "================================"
echo "Build Context: $CONTEXT"
echo "Registry: $REGISTRY"
echo "Image: $IMAGE"
echo "Version: $VERSION"
echo "Tag: $TAG"
echo ""

# Verify context exists
echo "Checking docker contexts..."
if ! docker context ls | grep -q "$CONTEXT"; then
    echo "❌ Context '$CONTEXT' not found"
    echo "Available contexts:"
    docker context ls
    exit 1
fi

# Switch to build context
echo "🔧 Using context: $CONTEXT"
export DOCKER_CONTEXT=$CONTEXT

# Check if logged in to registry
echo "Checking docker registry credentials..."
if ! docker info | grep -q "Registry"; then
    echo "⚠️  Not logged in to $REGISTRY"
    echo "Please login: docker --context $CONTEXT login $REGISTRY"
    exit 1
fi

# Build image
echo "📦 Building image on $CONTEXT..."
docker build \
    --build-arg VERSION=$VERSION \
    -t "$IMAGE:$TAG" \
    -t "$IMAGE:$VERSION" \
    -t "$IMAGE:latest" \
    .

echo "✓ Build completed"

# Push to registry
echo "🚀 Pushing to registry..."
docker push "$IMAGE:$TAG"
docker push "$IMAGE:$VERSION"
docker push "$IMAGE:latest"

echo ""
echo "================================"
echo "✓ Push completed successfully!"
echo "================================"
echo ""
echo "Image available at:"
echo "  • $IMAGE:$TAG"
echo "  • $IMAGE:$VERSION"
echo "  • $IMAGE:latest"
echo ""
echo "Deploy with:"
echo "  ./deploy.sh"
