#!/bin/bash

# AI-ONE Docker Swarm Deployment Script
# Usage: ./deploy.sh [init|deploy|update|rollback|remove|logs|status]

set -e

STACK_NAME="ai-one"
CONTEXT="swarm-prod"
REGISTRY="registry.p4tkry.pl"
IMAGE_NAME="${REGISTRY}/ai-one"
VERSION=${VERSION:-latest}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if context exists
check_context() {
    if ! docker context ls | grep -q "^${CONTEXT}"; then
        log_error "Docker context '$CONTEXT' not found"
        log_info "Available contexts:"
        docker context ls
        exit 1
    fi
    export DOCKER_CONTEXT=$CONTEXT
}

# Check if Docker Swarm is initialized
check_swarm() {
    check_context
    
    if ! docker info 2>/dev/null | grep -q "Swarm: active"; then
        log_error "Docker Swarm is not initialized on context '$CONTEXT'!"
        log_info "Run: docker --context $CONTEXT swarm init"
        exit 1
    fi
}

# Initialize Swarm
init_swarm() {
    check_context
    
    log_info "Initializing Docker Swarm on context '$CONTEXT'..."
    
    if docker info 2>/dev/null | grep -q "Swarm: active"; then
        log_warn "Swarm already initialized"
        return
    fi
    
    docker swarm init
    log_info "Swarm initialized successfully on context '$CONTEXT'"
    log_info "To add worker nodes, run the join command on worker machines"
}

# Create secrets
create_secrets() {
    log_info "Creating secrets on context '$CONTEXT'..."
    
    # Check if .env exists
    if [ ! -f .env ]; then
        log_error ".env file not found!"
        log_info "Copy .env.example to .env and configure it"
        exit 1
    fi
    
    # Load .env
    source .env
    
    # Create secrets if they don't exist
    if ! docker secret ls | grep -q "ai-one_credentials_password"; then
        echo -n "$CREDENTIALS_PASSWORD" | docker secret create ai-one_credentials_password - 2>/dev/null || log_warn "Secret ai-one_credentials_password already exists"
        log_info "Created secret: ai-one_credentials_password"
    fi
    
    if ! docker secret ls | grep -q "ai-one_messenger_token"; then
        echo -n "$MESSENGER_PAGE_ACCESS_TOKEN" | docker secret create ai-one_messenger_token - 2>/dev/null || log_warn "Secret ai-one_messenger_token already exists"
        log_info "Created secret: ai-one_messenger_token"
    fi
    
    if ! docker secret ls | grep -q "ai-one_messenger_page_id"; then
        echo -n "$MESSENGER_PAGE_ID" | docker secret create ai-one_messenger_page_id - 2>/dev/null || log_warn "Secret ai-one_messenger_page_id already exists"
        log_info "Created secret: ai-one_messenger_page_id"
    fi
    
    if [ -f "persistent/google_credentials.json" ]; then
        if ! docker secret ls | grep -q "ai-one_google_credentials"; then
            docker secret create ai-one_google_credentials persistent/google_credentials.json 2>/dev/null || log_warn "Secret ai-one_google_credentials already exists"
            log_info "Created secret: ai-one_google_credentials"
        fi
    else
        log_warn "Google credentials file not found: persistent/google_credentials.json"
    fi
}

# Setup volumes
setup_volumes() {
    log_info "Setting up volumes on context '$CONTEXT'..."
    
    # Note: Volumes must be prepared on the swarm nodes manually
    log_warn "Ensure these directories exist on all nodes:"
    log_info "  /mnt/nfs/ai-one/persistent"
    log_info "  /mnt/nfs/ai-one/logs"
}

# Deploy stack
deploy_stack() {
    check_swarm
    
    log_info "Deploying stack: ${STACK_NAME} to context '$CONTEXT'"
    
    # Create secrets
    create_secrets
    
    # Setup volumes
    setup_volumes
    
    # Pull latest image
    log_info "Pulling image from registry..."
    docker pull "${IMAGE_NAME}:${VERSION}" || log_warn "Could not pull image, using local"
    
    # Deploy
    docker stack deploy -c docker-compose.yml ${STACK_NAME}
    
    log_info "Stack deployed successfully!"
    log_info "Check status with: docker --context $CONTEXT stack services ${STACK_NAME}"
}

# Update stack
update_stack() {
    check_swarm
    
    log_info "Updating stack: ${STACK_NAME} on context '$CONTEXT'"
    
    # Pull latest image
    log_info "Pulling latest image..."
    docker pull "${IMAGE_NAME}:${VERSION}" || log_warn "Could not pull image"
    
    # Deploy (will do rolling update)
    docker stack deploy -c docker-compose.yml ${STACK_NAME}
    
    log_info "Stack updated successfully!"
}

# Rollback service
rollback_service() {
    check_swarm
    
    log_info "Rolling back service..."
    docker service rollback ${STACK_NAME}_ai-one
    log_info "Rollback initiated"
}

# Remove stack
remove_stack() {
    check_swarm
    
    log_warn "Removing stack: ${STACK_NAME}"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Cancelled"
        exit 0
    fi
    
    docker stack rm ${STACK_NAME}
    log_info "Stack removed"
    
    log_warn "Secrets are NOT removed. Remove manually if needed:"
    log_info "  docker --context $CONTEXT secret rm ai-one_credentials_password"
    log_info "  docker --context $CONTEXT secret rm ai-one_messenger_token"
    log_info "  docker --context $CONTEXT secret rm ai-one_messenger_page_id"
    log_info "  docker --context $CONTEXT secret rm ai-one_google_credentials"
}

# Show logs
show_logs() {
    check_swarm
    
    log_info "Showing logs for ${STACK_NAME}_ai-one"
    docker service logs -f ${STACK_NAME}_ai-one
}

# Show status
show_status() {
    check_swarm
    
    log_info "Stack services on context '$CONTEXT':"
    docker stack services ${STACK_NAME}
    
    echo ""
    log_info "Service tasks:"
    docker service ps ${STACK_NAME}_ai-one --no-trunc
    
    echo ""
    log_info "Secrets:"
    docker secret ls | grep ai-one
}

# Main
case "$1" in
    init)
        init_swarm
        ;;
    deploy)
        deploy_stack
        ;;
    update)
        update_stack
        ;;
    rollback)
        rollback_service
        ;;
    remove)
        remove_stack
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {init|deploy|update|rollback|remove|logs|status}"
        echo ""
        echo "Configuration:"
        echo "  Context: $CONTEXT"
        echo "  Registry: $REGISTRY"
        echo "  Stack: $STACK_NAME"
        echo ""
        echo "Commands:"
        echo "  init      - Initialize Docker Swarm on '$CONTEXT'"
        echo "  deploy    - Deploy stack (first time deployment)"
        echo "  update    - Update stack (rolling update)"
        echo "  rollback  - Rollback to previous version"
        echo "  remove    - Remove stack"
        echo "  logs      - Show service logs"
        echo "  status    - Show stack status"
        exit 1
        ;;
esac

# Initialize Swarm
init_swarm() {
    log_info "Initializing Docker Swarm..."
    
    if docker info 2>/dev/null | grep -q "Swarm: active"; then
        log_warn "Swarm already initialized"
        return
    fi
    
    docker swarm init
    log_info "Swarm initialized successfully"
    log_info "To add worker nodes, run the join command on worker machines"
}

# Create secrets
create_secrets() {
    log_info "Creating secrets..."
    
    # Check if .env exists
    if [ ! -f .env ]; then
        log_error ".env file not found!"
        log_info "Copy .env.example to .env and configure it"
        exit 1
    fi
    
    # Load .env
    source .env
    
    # Create secrets if they don't exist
    if ! docker secret ls | grep -q "ai-one_credentials_password"; then
        echo -n "$CREDENTIALS_PASSWORD" | docker secret create ai-one_credentials_password - 2>/dev/null || log_warn "Secret ai-one_credentials_password already exists"
        log_info "Created secret: ai-one_credentials_password"
    fi
    
    if ! docker secret ls | grep -q "ai-one_messenger_token"; then
        echo -n "$MESSENGER_PAGE_ACCESS_TOKEN" | docker secret create ai-one_messenger_token - 2>/dev/null || log_warn "Secret ai-one_messenger_token already exists"
        log_info "Created secret: ai-one_messenger_token"
    fi
    
    if ! docker secret ls | grep -q "ai-one_messenger_page_id"; then
        echo -n "$MESSENGER_PAGE_ID" | docker secret create ai-one_messenger_page_id - 2>/dev/null || log_warn "Secret ai-one_messenger_page_id already exists"
        log_info "Created secret: ai-one_messenger_page_id"
    fi
    
    if [ -f "persistent/google_credentials.json" ]; then
        if ! docker secret ls | grep -q "ai-one_google_credentials"; then
            docker secret create ai-one_google_credentials persistent/google_credentials.json 2>/dev/null || log_warn "Secret ai-one_google_credentials already exists"
            log_info "Created secret: ai-one_google_credentials"
        fi
    else
        log_warn "Google credentials file not found: persistent/google_credentials.json"
    fi
}

# Setup volumes
setup_volumes() {
    log_info "Setting up volumes..."
    
    # Create directories
    sudo mkdir -p /mnt/nfs/ai-one/persistent
    sudo mkdir -p /mnt/nfs/ai-one/logs
    
    # Copy persistent files if they exist
    if [ -d "persistent" ]; then
        log_info "Copying persistent files..."
        sudo cp -r persistent/* /mnt/nfs/ai-one/persistent/ 2>/dev/null || true
    fi
    
    # Set permissions
    sudo chown -R 1000:1000 /mnt/nfs/ai-one
    
    log_info "Volumes setup completed"
}

# Build image
build_image() {
    log_info "Building Docker image..."
    docker build -t ${IMAGE_NAME}:${VERSION} .
    log_info "Image built successfully: ${IMAGE_NAME}:${VERSION}"
}

# Deploy stack
deploy_stack() {
    check_swarm
    
    log_info "Deploying stack: ${STACK_NAME}"
    
    # Create secrets
    create_secrets
    
    # Setup volumes
    setup_volumes
    
    # Build image
    build_image
    
    # Deploy
    docker stack deploy -c docker-compose.yml ${STACK_NAME}
    
    log_info "Stack deployed successfully!"
    log_info "Check status with: docker stack services ${STACK_NAME}"
}

# Update stack
update_stack() {
    check_swarm
    
    log_info "Updating stack: ${STACK_NAME}"
    
    # Build new image
    build_image
    
    # Deploy (will do rolling update)
    docker stack deploy -c docker-compose.yml ${STACK_NAME}
    
    log_info "Stack updated successfully!"
}

# Rollback service
rollback_service() {
    check_swarm
    
    log_info "Rolling back service..."
    docker service rollback ${STACK_NAME}_ai-one
    log_info "Rollback initiated"
}

# Remove stack
remove_stack() {
    check_swarm
    
    log_warn "Removing stack: ${STACK_NAME}"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Cancelled"
        exit 0
    fi
    
    docker stack rm ${STACK_NAME}
    log_info "Stack removed"
    
    log_warn "Secrets are NOT removed. Remove manually if needed:"
    log_info "  docker secret rm ai-one_credentials_password"
    log_info "  docker secret rm ai-one_messenger_token"
    log_info "  docker secret rm ai-one_messenger_page_id"
    log_info "  docker secret rm ai-one_google_credentials"
}

# Show logs
show_logs() {
    check_swarm
    
    log_info "Showing logs for ${STACK_NAME}_ai-one"
    docker service logs -f ${STACK_NAME}_ai-one
}

# Show status
show_status() {
    check_swarm
    
    log_info "Stack services:"
    docker stack services ${STACK_NAME}
    
    echo ""
    log_info "Service tasks:"
    docker service ps ${STACK_NAME}_ai-one --no-trunc
    
    echo ""
    log_info "Secrets:"
    docker secret ls | grep ai-one
}

# Main
case "$1" in
    init)
        init_swarm
        ;;
    deploy)
        deploy_stack
        ;;
    update)
        update_stack
        ;;
    rollback)
        rollback_service
        ;;
    remove)
        remove_stack
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {init|deploy|update|rollback|remove|logs|status}"
        echo ""
        echo "Commands:"
        echo "  init      - Initialize Docker Swarm"
        echo "  deploy    - Deploy stack (first time deployment)"
        echo "  update    - Update stack (rolling update)"
        echo "  rollback  - Rollback to previous version"
        echo "  remove    - Remove stack"
        echo "  logs      - Show service logs"
        echo "  status    - Show stack status"
        exit 1
        ;;
esac
