# AI-ONE Deployment Guide

> AI-ONE behind Traefik on Docker Swarm

## Quick Start

```bash
# 1. Build image on desktop-linux
./build_and_push.sh 1.0 latest

# 2. Deploy to swarm-prod
./deploy.sh deploy

# 3. Access
https://ai-one.p4tkry.pl
```

## Architecture

```
Internet (HTTPS 443)
         |
    Traefik v3.6.1 (already running on swarm-prod)
         |
    [traefik_proxy overlay network]
         |
    ai-one service (this stack)
         |
    Application (port 8000, internal only)
```

## Separate Build & Deploy Contexts

### desktop-linux (Build)
- Local build machine
- `./build_and_push.sh` → pushes to `registry.p4tkry.pl`
- Image stored as artifact in registry

### swarm-prod (Deploy)
- Docker Swarm cluster
- `./deploy.sh deploy` → pulls from registry, deploys stack
- Traefik automatically discovers labels, routes traffic

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Stack definition (ai-one only, Traefik external) |
| `build_and_push.sh` | Build & push script (uses desktop-linux context) |
| `deploy.sh` | Deploy & manage script (uses swarm-prod context) |
| `Dockerfile` | Image definition (includes ffmpeg for Whisper) |
| `requirements.txt` | Python dependencies |
| `.env` | Configuration (secrets, paths, API keys) |

## Configuration

### Build Context: desktop-linux

```bash
./build_and_push.sh [VERSION] [TAG]

# Examples:
./build_and_push.sh 1.0 latest
./build_and_push.sh 1.1 release
```

What happens:
1. Switches to `desktop-linux` context
2. Builds Docker image
3. Tags as `registry.p4tkry.pl/ai-one:VERSION`
4. Pushes to registry

### Deploy Context: swarm-prod

```bash
./deploy.sh [COMMAND]

# Commands:
./deploy.sh init      # Initialize Swarm (first time)
./deploy.sh deploy    # Deploy stack
./deploy.sh update    # Rolling update
./deploy.sh status    # Show status
./deploy.sh logs      # Show logs
./deploy.sh rollback  # Rollback to previous
./deploy.sh remove    # Remove stack
```

## Traefik Integration

### Docker Swarm Provider

Traefik watches Swarm labels and auto-discovers services:

```yaml
deploy:
  labels:
    - traefik.enable=true
    - traefik.http.routers.ai-one.rule=Host(`ai-one.p4tkry.pl`)
    - traefik.http.routers.ai-one.entrypoints=websecure
    - traefik.http.routers.ai-one.tls.certresolver=le
    - traefik.http.services.ai-one.loadbalancer.server.port=8000
```

### Network

- `traefik_proxy`: External overlay network
- Created by Traefik stack
- Enables service discovery

### Routing

- Hostname: `ai-one.p4tkry.pl`
- EntryPoint: `websecure` (HTTPS only)
- TLS: Let's Encrypt (automatic)
- Backend port: `8000`

## Secrets Management

All secrets stored in Docker Swarm (not in env vars):

```bash
# Docker automatically manages these:
- ai-one_credentials_password
- ai-one_messenger_token
- ai-one_messenger_page_id
- ai-one_google_credentials
```

## Volumes

| Volume | Path | Purpose |
|--------|------|---------|
| persistent_data | /data/ai-one/persistent | Persistent files (SOUL.md, etc) |
| app_logs | /data/ai-one/logs | Application logs |

## Deployment Workflow

### First Time Setup

```bash
# 1. Verify contexts exist
docker context ls

# 2. Build image
./build_and_push.sh 1.0 latest

# 3. Initialize Swarm (first time only)
./deploy.sh init

# 4. Deploy stack
./deploy.sh deploy

# 5. Verify
./deploy.sh status
https://ai-one.p4tkry.pl
```

### Updates

```bash
# 1. Build new version
./build_and_push.sh 1.1 latest

# 2. Deploy update (rolling)
./deploy.sh update

# No downtime, old replicas stop after new ones start
```

### Rollback

```bash
./deploy.sh rollback

# Reverts to previous version
```

## Troubleshooting

### Service not running

```bash
./deploy.sh status
./deploy.sh logs
```

### Not accessible at ai-one.p4tkry.pl

1. Check Traefik is running:
   ```bash
   docker --context swarm-prod service ls | grep traefik
   ```

2. Check service labels:
   ```bash
   docker --context swarm-prod service inspect ai-one_ai-one | grep traefik
   ```

### Build failed

```bash
# Switch to build context
export DOCKER_CONTEXT=desktop-linux

# Check login
docker login registry.p4tkry.pl

# Retry build
./build_and_push.sh 1.0 latest
```

### Deploy failed

```bash
# Check context
export DOCKER_CONTEXT=swarm-prod

# Verify Swarm is active
docker info | grep "Swarm: active"

# Check network
docker network ls | grep traefik_proxy
```

## Key Features

✓ **Separate Build/Deploy**: desktop-linux for builds, swarm-prod for deployments  
✓ **Registry Artifacts**: Images stored in registry.p4tkry.pl  
✓ **Automatic HTTPS**: Let's Encrypt certificates via Traefik  
✓ **Zero-Downtime Updates**: Rolling updates with Swarm  
✓ **Auto-Discovery**: Traefik finds services via labels  
✓ **Secrets Management**: Docker Swarm secrets  
✓ **Load Balancing**: Traefik balances across replicas  
✓ **Monitoring**: Status, logs, metrics  

## Environment Variables

See `.env` for configuration:
- `CREDENTIALS_PASSWORD` - Encryption key for credentials
- `SOUL_PATH` - System instructions file
- `USER_PATH` - User information file
- `MEMORY_PATH` - Memory/context file
- `MESSENGER_PAGE_ACCESS_TOKEN` - Facebook Messenger token
- `MESSENGER_PAGE_ID` - Facebook Page ID
- `GOOGLE_CREDENTIALS_PATH` - Google Workspace credentials
- `GOOGLE_TOKEN_PATH` - Google Workspace token

## Scaling

Scale ai-one replicas:

```yaml
# docker-compose.yml
deploy:
  replicas: 3  # Run 3 instances
```

Traefik automatically load-balances between replicas.

## Performance

- CPU limits: 2.0
- Memory limits: 2GB
- CPU reservation: 0.5
- Memory reservation: 512MB
- Restart: on-failure (max 3 attempts)

## Documentation

- `TRAEFIK_INTEGRATION.md` - Traefik configuration details
- `DOCKER_CONTEXTS.md` - Docker context setup guide

## Support

Check logs for issues:

```bash
./deploy.sh logs          # AI-ONE logs
```

Note: Traefik is a separate external stack. Check Traefik logs with:
```bash
docker --context swarm-prod service logs traefik_traefik
```

## Security Notes

1. **HTTPS Only**: No HTTP, all traffic encrypted via Traefik
2. **Secrets**: Protected by Docker Swarm (not exposed in containers)
3. **Network**: Private overlay network, not exposed to host
4. **TLS**: Automatic certificate renewal via Let's Encrypt
5. **Registry**: Login with docker login registry.p4tkry.pl

---

**Ready to deploy!** Run `./build_and_push.sh && ./deploy.sh deploy`
