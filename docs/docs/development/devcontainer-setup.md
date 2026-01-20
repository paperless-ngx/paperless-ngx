---
sidebar_position: 2
title: Development Container Setup
description: VSCode DevContainer configuration for Paperless NGX development
---

# Development Container Setup

This guide explains the VSCode DevContainer setup for Paperless NGX development. DevContainers provide a consistent, containerized development environment that eliminates "works on my machine" issues.

## Overview

The Paperless NGX project includes a complete DevContainer configuration that provisions:

- **Base Environment**: Node 24 with Python runtime and system dependencies
- **Services**: Redis (message broker), Gotenberg (document converter), Apache Tika (document processing)
- **Storage**: Docker volumes for persistent data across container restarts
- **IDE Integration**: VSCode extensions and debugging configurations

This setup allows you to develop within a Docker container while using VSCode running on your host machine.

## What Are DevContainers?

DevContainers (Development Containers) are a standardized way to define development environments in containers. Benefits include:

- **Consistency**: All developers use identical environment regardless of host OS
- **Isolation**: Development dependencies don't affect your local machine
- **Reproducibility**: Easily recreate the environment on any machine with Docker
- **Pre-configured**: All tools, dependencies, and services pre-installed in container
- **Onboarding**: New developers get setup quickly without manual configuration

## Getting Started

### Prerequisites

- **Docker Desktop** or Docker Engine
- **VSCode** with [Remote - Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- **4+ GB RAM** allocated to Docker
- **20+ GB disk space** for container and development files

### Step 1: Open Project in DevContainer

1. Clone the Paperless NGX repository:
   ```bash
   git clone https://github.com/paperless-ngx/paperless-ngx.git
   cd paperless-ngx
   ```

2. Open the project folder in VSCode:
   ```bash
   code .
   ```

3. When VSCode detects the `.devcontainer` configuration, click **"Reopen in Container"** in the dialog, or:
   - Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`)
   - Select **"Dev Containers: Rebuild and Reopen in Container"**

VSCode will build the container image and start the development environment.

### Step 2: Initialize Project

Once the container is running:

1. Open the Command Palette
2. Select **"Tasks: Run Task"**
3. Choose **"Project Setup: Run all Init Tasks"**

This runs:
- Frontend compilation (`npm run build`)
- Database migrations (`manage.py migrate`)
- Superuser creation (`manage.py createsuperuser`)

Alternatively, run individual tasks:

```bash
# In DevContainer terminal
pnpm run build                          # Compile frontend
python manage.py migrate                # Apply database migrations
python manage.py createsuperuser        # Create admin user
```

### Step 3: Start Backend Services

Choose one method to run the backend:

**Using VSCode Debugger (Recommended)**:
1. Press `F5` or go to **Run and Debug** view
2. Select a configuration:
   - **"Runserver"** - Web development server
   - **"Document Consumer"** - File processor
   - **"Celery"** - Async task worker

**Using Tasks**:
1. Open Command Palette
2. Select **"Tasks: Run Task"**
3. Choose desired task

## Configuration Files

### `.devcontainer/devcontainer.json`

Main configuration file defining the container setup:

```json
{
  "name": "Paperless Development",
  "dockerComposeFile": "docker-compose.devcontainer.sqlite-tika.yml",
  "service": "paperless-development",
  "workspaceFolder": "/usr/src/paperless/paperless-ngx",
  "postCreateCommand": "uv sync --group dev && uv run pre-commit install"
}
```

**Key Settings**:
- **service**: Container where VSCode connects
- **workspaceFolder**: Your repository location in container
- **postCreateCommand**: Runs after container creation (installs dependencies, sets up git hooks)

### `.devcontainer/docker-compose.devcontainer.sqlite-tika.yml`

Defines all services needed for development:

**Services**:
- **paperless-development**: Main container with Python, Node.js, and system tools
- **redis**: Message broker for Celery (port 6379)
- **gotenberg**: Document format converter (port 3000)
- **tika**: Office document processor (port 9998)

**Volumes**:
- **virtualenv**: Python virtual environment (`.venv`)
- **data/media/consume**: Document storage
- **redisdata**: Redis persistence

:::info Storage Volumes
All volumes are Docker-managed and persist across container restarts. The main code is mounted from your host machine (synchronized in real-time), while generated files like `.venv` stay in the container.
:::

### `.devcontainer/Dockerfile`

Builds the development container image from Node 24 base:

**Includes**:
- Python runtime and build tools
- System packages (ImageMagick, Tesseract OCR, PostgreSQL/MySQL clients)
- Docker tooling and user setup
- Volume mounts for data persistence

## Available VSCode Configurations

### Debugging (F5)

Pre-configured launch configurations in `.devcontainer/vscode/launch.json`:

| Configuration | Purpose | Language |
|---|---|---|
| Runserver | Django development server | Python |
| Document Consumer | File document processor | Python |
| Celery | Background task worker | Python |
| Chrome: Debug Angular Frontend | Frontend debugging | TypeScript/JavaScript |

### Tasks

Pre-configured tasks in `.devcontainer/vscode/tasks.json`:

**Project Setup**:
- `Project Setup: Run all Init Tasks` - Complete initialization

**Development**:
- `Runserver` - Start Django development server
- `Document Consumer` - Start document processor
- `Celery` - Start async task worker

**Maintenance**:
- `Maintenance: Compile frontend for production` - Build frontend assets
- `Maintenance: manage.py migrate` - Apply database migrations
- `Maintenance: manage.py createsuperuser` - Create admin user
- `Maintenance: Recreate .venv` - Rebuild Python environment

### Extensions

Automatically installed in the container:

- **Python** - Python IntelliSense, debugging, linting
- **GitLens** - Enhanced git integration
- **Markdown All in One** - Markdown editing support
- **JavaScript Debugger Nightly** - Advanced JS debugging
- **Git Graph** - Visual git history

## Development Workflow

### Working with Code

1. **Edit files** on your host machine - changes sync automatically to container
2. **Run services** inside the container using debugger or tasks
3. **View logs** in VSCode terminal or debug console
4. **Access services**:
   - **Web UI**: http://localhost:8000
   - **Redis**: `redis-cli` in container terminal
   - **PostgreSQL**: `psql` command if using Postgres variant

### Database

**Default Database**: SQLite (file-based, no external service needed)

**Alternative**: PostgreSQL available via `docker-compose.devcontainer.postgres-tika.yml`

To use PostgreSQL:
1. Edit `.devcontainer/devcontainer.json`
2. Change `dockerComposeFile` to:
   ```json
   "dockerComposeFile": "docker-compose.devcontainer.postgres-tika.yml"
   ```
3. Rebuild container

### Running Tests

```bash
# Backend tests (Python)
pytest src/

# Frontend tests (TypeScript)
npm run test

# All tests with coverage
pytest --cov src/
npm run test:coverage
```

### Installing Dependencies

**Backend** (Python):
```bash
# Using uv package manager
uv add package-name      # Add package
uv sync                  # Install from pyproject.toml
```

**Frontend** (Node.js):
```bash
# Using pnpm
pnpm add package-name
pnpm install
```

## Troubleshooting

### Container Won't Start

**Check Docker**: Ensure Docker is running and has sufficient resources

```bash
docker ps
docker system df
```

**Rebuild Container**:
```bash
# Delete and rebuild
Dev Containers: Rebuild Container
```

### Port Already in Use

If ports 8000, 6379, 3000, or 9998 are in use on your host:

1. Identify process: `lsof -i :PORT`
2. Modify `.devcontainer/docker-compose.devcontainer.sqlite-tika.yml` port mappings
3. Rebuild container

### Slow Performance

**On Mac/Windows**: File synchronization can be slow

- Use `:delegated` mounts (configured by default)
- Exclude large directories from mount
- Check Docker resource allocation

### Virtual Environment Issues

If Python dependencies seem incorrect:

1. Open terminal in container
2. Run task: **"Maintenance: Recreate .venv"**
3. Restart debugger

### Git Credentials

DevContainer inherits host machine's git credentials. If needed:

```bash
# Inside container terminal
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## Storage and Persistence

### What Persists

These are stored in Docker volumes and survive container restarts:
- `.venv` - Python environment
- `data/` - Paperless data directory
- `media/` - Processed documents
- `consume/` - Import folder
- `redisdata/` - Redis cache

### What's Ephemeral

These are deleted when container stops:
- Container filesystem (except volumes)
- Temporary files and caches (`.pytest_cache`, `.ruff_cache`)

To clean up:
```bash
# Clean build artifacts
rm -rf .pytest_cache .ruff_cache htmlcov

# Full reset (deletes volumes)
Dev Containers: Remove Container
```

## Advanced Configuration

### Using Different Database

Edit `.devcontainer/devcontainer.json` to use PostgreSQL:

```json
"dockerComposeFile": "docker-compose.devcontainer.postgres-tika.yml"
```

### Custom Environment Variables

Create `.env.devcontainer` in project root for local overrides:

```bash
PAPERLESS_DEBUG=1
PAPERLESS_WORKER_THREADS=4
```

### Adding System Packages

Edit `.devcontainer/Dockerfile` and rebuild container:

```dockerfile
RUN apt-get update && apt-get install -y package-name
```

## Performance Tuning

### Reduce Build Time

First build takes longer. Subsequent rebuilds cache layers:
- Don't modify `Dockerfile` frequently
- Minimize `postCreateCommand` changes

### Optimize File Sync

Mount options in `docker-compose.devcontainer.sqlite-tika.yml`:
```yaml
volumes:
  - ..:/usr/src/paperless/paperless-ngx:delegated
```

- `:delegated` - Host changes sync to container (faster)
- `:cached` - Container changes sync to host (slower)
- `:rprivate` - No syncing (use for large directories)

## References

- [VSCode DevContainers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [Docker Documentation](https://docs.docker.com/)
- [Paperless NGX Repository](https://github.com/paperless-ngx/paperless-ngx)

## Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review DevContainer logs in VSCode
3. Check `.devcontainer/README.md` for additional notes
4. Open an issue on [GitHub](https://github.com/paperless-ngx/paperless-ngx/issues)

---

**Last Updated**: 2026-01-20

Created for VSCode DevContainer integration documentation.
