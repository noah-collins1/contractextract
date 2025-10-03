# LibreChat MCP stdio Setup - Verification & Startup Guide

## ✅ What We Fixed

### Problem
You had **two conflicting backend services**:
1. `api` service in `docker-compose.yml`
2. `web` service in `docker-compose.override.yml`

Both were trying to use port 3080, and the `web` service:
- Wasn't inheriting dependencies from the base `api` service
- Had `MONGO_URI` but the base service uses `MONGO_URI` (different var name)
- Wasn't waiting for MongoDB to be healthy before starting

### Solution
**Normalized to single `api` service** by properly overriding it in `docker-compose.override.yml`:
- ✅ Builds custom image with Python (`Dockerfile.librechat-python`)
- ✅ Mounts MCP server code from `C:\Users\noahc\PycharmProjects\langextract`
- ✅ Installs Python dependencies in venv at `/opt/mcp/.venv`
- ✅ Waits for MongoDB health check before starting
- ✅ Properly configured `MONGO_URI` environment variable

## 📁 Modified Files

1. **`Dockerfile.librechat-python`**
   - Extends official LibreChat image
   - Installs Python 3, pip, build tools (Alpine)
   - Creates virtualenv at `/opt/mcp/.venv`
   - Installs MCP dependencies from `mcp-requirements.txt`

2. **`docker-compose.override.yml`**
   - Overrides `api` service (not creating new `web` service)
   - Builds with custom Dockerfile
   - Mounts librechat.yaml and MCP code
   - Sets all required environment variables including `MONGO_URI`
   - Adds health check dependencies

3. **`librechat.yaml`**
   - MCP server config under `mcpServers.contractextract`
   - Uses venv Python: `/opt/mcp/.venv/bin/python`
   - stdio type with proper timeouts

4. **`mcp-requirements.txt`**
   - Copied from your MCP project's requirements.txt
   - Used during Docker build to install dependencies

## 🚀 Startup Sequence

### First Time Setup
```bash
# 1. Ensure you're in LibreChat directory
cd C:\Users\noahc\LibreChat

# 2. Verify merged config is valid
docker compose config --services
# Expected output: meilisearch, mongodb, vectordb, rag_api, api

# 3. Build the custom image with Python + MCP dependencies
docker compose build api

# 4. Start all services with dependency ordering
docker compose up -d

# 5. Check service status
docker compose ps
# All services should show "Up" or "running"
```

### Verification Steps
```bash
# Check MongoDB is healthy
docker compose ps mongodb
# Should show: Up (healthy)

# Check api service is running
docker compose ps api
# Should show: Up

# Verify Python is installed
docker compose exec api python3 -V
# Expected: Python 3.x.x

# Verify MCP code is mounted
docker compose exec api ls -la /opt/mcp/contractextract
# Should list: mcp_server.py, requirements.txt, etc.

# Verify venv and MCP SDK installed
docker compose exec api /opt/mcp/.venv/bin/python -c "import mcp; print('MCP SDK OK')"
# Expected: MCP SDK OK

# Check LibreChat logs for MCP initialization
docker compose logs -f api | grep -i "mcp\|contractextract"
# Look for MCP server startup messages
```

## 📊 Service Dependency Graph

```
api (LibreChat + Python)
├── mongodb (healthy) ✅
├── meilisearch (healthy) ✅
└── rag_api (started) ✅

mongodb (Mongo 7 with healthcheck)
meilisearch (with healthcheck)
rag_api (with healthcheck)
└── mongodb (healthy) ✅
└── meilisearch (healthy) ✅

vectordb (PostgreSQL with pgvector)
```

## 🔧 Common Operations

### View Logs
```bash
# All services
docker compose logs -f

# Just LibreChat
docker compose logs -f api

# Just MongoDB
docker compose logs -f mongodb

# Filter for MCP-related messages
docker compose logs -f api | grep -i mcp
```

### Restart After Changes

**If you change `librechat.yaml` only:**
```bash
docker compose restart api
```

**If you change MCP code (Python files):**
- No restart needed! The code is mounted as a volume
- MCP server will be respawned on next agent invocation

**If you change `mcp-requirements.txt` (new dependencies):**
```bash
# 1. Copy updated requirements
cp C:/Users/noahc/PycharmProjects/langextract/requirements.txt mcp-requirements.txt

# 2. Rebuild image
docker compose build --no-cache api

# 3. Recreate container
docker compose up -d --force-recreate api
```

**If you change `Dockerfile.librechat-python`:**
```bash
docker compose build --no-cache api
docker compose up -d --force-recreate api
```

### Stop Services
```bash
# Stop all
docker compose down

# Stop but keep volumes (faster restart)
docker compose stop

# Start again
docker compose up -d
```

### Clean Restart
```bash
# Remove all containers and volumes
docker compose down -v

# Rebuild and start fresh
docker compose build api
docker compose up -d
```

## 🐛 Troubleshooting

### Error: `Please define the MONGO_URI environment variable`

**Cause:** Environment variable not passed to container

**Fix:**
```bash
# Check merged config
docker compose config | grep MONGO_URI

# Should show under services.api.environment:
#   MONGO_URI: mongodb://mongodb:27017/LibreChat
```

If missing, verify `docker-compose.override.yml` has:
```yaml
services:
  api:
    environment:
      - MONGO_URI=mongodb://mongodb:27017/LibreChat
```

### Error: `getaddrinfo ENOTFOUND mongodb`

**Cause:** MongoDB service not running or not healthy when api started

**Fix:**
```bash
# Check MongoDB status
docker compose ps mongodb
# Should show: Up (healthy)

# If not healthy, check logs
docker compose logs mongodb

# Restart with proper order
docker compose down
docker compose up -d mongodb  # Start MongoDB first
# Wait ~20 seconds for health check
docker compose up -d api      # Then start api
```

### MCP Server Won't Initialize

**Symptoms:** No MCP logs, tools not available in LibreChat

**Debugging:**
```bash
# 1. Check Python and code are present
docker compose exec api ls -la /opt/mcp/contractextract
docker compose exec api /opt/mcp/.venv/bin/python -V

# 2. Test MCP server manually
docker compose exec api /opt/mcp/.venv/bin/python /opt/mcp/contractextract/mcp_server.py
# Should start without errors

# 3. Check for missing dependencies
docker compose exec api /opt/mcp/.venv/bin/pip list | grep mcp
# Should show: mcp 1.14.1

# 4. Check librechat.yaml syntax
docker compose exec api cat /app/librechat.yaml | grep -A 15 "mcpServers:"
```

### Permission Errors on Mount

**Symptoms:** "Permission denied" when accessing `/opt/mcp/contractextract`

**Fix:** Change mount from read-only to read-write in `docker-compose.override.yml`:
```yaml
volumes:
  - C:\Users\noahc\PycharmProjects\langextract:/opt/mcp/contractextract  # Remove :ro
```

### Port 3080 Already in Use

**Cause:** Old container or another service using the port

**Fix:**
```bash
# Find what's using the port
netstat -ano | findstr :3080

# Stop all compose services
docker compose down

# Remove all LibreChat containers
docker ps -a | grep librechat
docker rm -f LibreChat

# Start fresh
docker compose up -d
```

## 📝 Architecture Summary

```
┌─────────────────────────────────────────────┐
│  Windows Host                               │
│  C:\Users\noahc\PycharmProjects\langextract │
│  ├── mcp_server.py                          │
│  ├── requirements.txt                       │
│  └── ... (MCP server code)                  │
└──────────────────┬──────────────────────────┘
                   │ Mounted as volume
                   ▼
┌─────────────────────────────────────────────┐
│  LibreChat Container (api service)          │
│  ┌────────────────────────────────────┐     │
│  │ Node.js (LibreChat backend)        │     │
│  │  └── Spawns stdio MCP server ──┐   │     │
│  └──────────────────────────────────┼───┘   │
│                                     │       │
│  ┌──────────────────────────────────▼───┐   │
│  │ Python venv: /opt/mcp/.venv          │   │
│  │  ├── mcp SDK (1.14.1)                │   │
│  │  ├── langextract (1.0.9)             │   │
│  │  └── all dependencies                │   │
│  └──────────────────────────────────────┘   │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │ Mounted code: /opt/mcp/contractextract │ │
│  │  (read-only from Windows host)       │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## ✅ Success Indicators

When everything works correctly:

1. **`docker compose ps`** shows all services "Up" or "healthy"
2. **LibreChat accessible** at http://localhost:3080
3. **MCP server appears** in agent tools/capabilities
4. **Logs show MCP initialization:** `docker compose logs api | grep -i mcp`
5. **No MONGO_URI errors** in logs
6. **No ENOTFOUND mongodb** errors

## 🎯 Next Steps

Once the stack is running:

1. **Create/Login** to LibreChat at http://localhost:3080
2. **Create an Agent** with MCP tools enabled
3. **Select contractextract** MCP server in agent configuration
4. **Test the agent** with a contract document

Happy chatting! 🚀
