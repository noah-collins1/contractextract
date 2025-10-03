# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LibreChat is a full-stack AI chat platform supporting multiple AI providers (OpenAI, Anthropic, Google, AWS Bedrock, Azure, etc.) with advanced features including agents, Model Context Protocol (MCP) integration, file handling, and enterprise authentication. Built as a monorepo with shared packages.

**Version:** v0.8.0-rc4

## 🚨 CRITICAL DEPLOYMENT CONSTRAINTS

**This is a Docker Compose deployment. You can ONLY modify these files:**

1. **`Dockerfile.librechat-python`** - Custom image with Python for MCP stdio servers
2. **`librechat.yaml`** - LibreChat configuration (endpoints, MCP servers, interface)
3. **`docker-compose.override.yml`** - Docker Compose overrides (services, volumes, env)
4. **`.env`** - Environment variables
5. **`mcp-requirements.txt`** - Python dependencies for MCP server (copied from host)

**DO NOT modify:**
- Any source code in `api/`, `client/`, `packages/` directories
- The base `docker-compose.yml` file
- Any files that would require rebuilding the main LibreChat application

**Why:** This deployment is designed to run the official LibreChat Docker images with minimal customization to avoid breaking the production environment.

## Common Development Commands

### Setup & Installation
```bash
# Install dependencies
npm install

# Alternative with Bun
bun install
```

### Development
```bash
# Start backend in development mode
npm run backend:dev

# Start frontend development server
npm run frontend:dev

# Alternative with Bun
bun run b:api:dev
bun run b:client:dev
```

### Building
```bash
# Build frontend (builds all dependencies in order)
npm run frontend

# Build individual packages
npm run build:data-provider
npm run build:data-schemas
npm run build:api
npm run build:client-package

# Build with Bun
bun run b:client
```

### Testing
```bash
# Run client tests
npm run test:client
npm run test:client -- --watch  # Watch mode

# Run API tests
npm run test:api

# Run single test file
cd client && npm test -- path/to/test.spec.js

# E2E tests
npm run e2e                    # Headless
npm run e2e:headed             # With browser
npm run e2e:debug              # Debug mode
```

### Linting & Formatting
```bash
# Lint all files
npm run lint

# Fix linting issues
npm run lint:fix

# Format code
npm run format
```

### User Management
```bash
# Create user
npm run create-user

# Reset password
npm run reset-password

# List users
npm run list-users

# Ban/delete user
npm run ban-user
npm run delete-user
```

### Database Operations
```bash
# Add balance to user
npm run add-balance

# List user balances
npm run list-balances

# Reset Meilisearch sync
npm run reset-meili-sync

# Run migrations
npm run migrate:agent-permissions
npm run migrate:prompt-permissions
```

### Docker
```bash
# Build custom image with Python + MCP dependencies
docker compose build api

# Start all services
docker compose up -d

# Start specific services
docker compose up -d mongodb  # Start MongoDB first
docker compose up -d api      # Then start LibreChat

# Stop services
docker compose down

# View logs
docker compose logs -f api

# Check service status
docker compose ps

# Verify Python and MCP code are present
docker compose exec api python3 -V
docker compose exec api ls -la /opt/mcp/contractextract
docker compose exec api /opt/mcp/.venv/bin/python -c "import mcp; print('MCP SDK installed')"

# Rebuild after changes to Dockerfile or requirements
docker compose build --no-cache api
docker compose up -d --force-recreate api
```

### MCP stdio Server Setup (Current Deployment)

**Architecture:**
- MCP server code lives at: `C:\Users\noahc\PycharmProjects\langextract` (Windows host)
- Mounted inside container at: `/opt/mcp/contractextract`
- Python venv with dependencies at: `/opt/mcp/.venv`
- LibreChat spawns MCP server via stdio (not HTTP/FastAPI)

**Files involved:**
1. **`Dockerfile.librechat-python`**: Extends official LibreChat image with Python
2. **`mcp-requirements.txt`**: Copied from host MCP project (`langextract/requirements.txt`)
3. **`docker-compose.override.yml`**: Mounts MCP code and builds custom image
4. **`librechat.yaml`**: Configures stdio MCP server under `mcpServers.contractextract`

**Workflow when updating MCP dependencies:**
```bash
# 1. Update requirements in your MCP project
# Edit: C:\Users\noahc\PycharmProjects\langextract\requirements.txt

# 2. Copy to LibreChat build context
cp C:/Users/noahc/PycharmProjects/langextract/requirements.txt mcp-requirements.txt

# 3. Rebuild image with new dependencies
docker compose build --no-cache api

# 4. Restart LibreChat
docker compose up -d --force-recreate api

# 5. Verify MCP server initialization in logs
docker compose logs -f api | grep -i "mcp\|contractextract"
```

**Common issues:**
- **`ENOTFOUND mongodb`**: MongoDB service not running or not healthy. Check: `docker compose ps mongodb`
- **`Please define MONGO_URI`**: Environment variable not passed. Verify in `docker-compose.override.yml`
- **MCP server won't start**: Check Python dependencies installed. Exec into container and test manually:
  ```bash
  docker compose exec api /opt/mcp/.venv/bin/python /opt/mcp/contractextract/mcp_server.py
  ```
- **Permission errors on mounted volume**: Ensure mount is readable. Change `:ro` to `:rw` if MCP writes logs/temp files

## High-Level Architecture

### Monorepo Structure

LibreChat uses npm workspaces with the following structure:

```
LibreChat/
├── api/                     # Backend Express server
├── client/                  # Frontend React/Vite app
├── packages/
│   ├── data-provider/      # API client & data access layer
│   ├── data-schemas/       # Mongoose schemas & validation
│   ├── api/                # MCP services (@librechat/api)
│   └── client/             # Shared React components
└── config/                 # CLI utilities & scripts
```

**Build Dependencies:**
- `data-schemas` has no dependencies
- `data-provider` depends on `data-schemas`
- `api` package depends on `data-schemas`
- `client` package depends on `data-provider`, `data-schemas`, and `api`
- Frontend build runs: `data-provider` → `data-schemas` → `api` → `client` → `client` app

### Backend Architecture

**Entry Point:** `api/server/index.js`

**Key Components:**
- **Routes:** RESTful API organized by resource (`api/server/routes/`)
  - `/api/auth`, `/api/user`, `/api/convos`, `/api/messages`, `/api/agents`, `/api/assistants`, `/api/files`, `/api/mcp`, etc.
- **Controllers:** Request handlers (`api/server/controllers/`)
- **Services:** Business logic layer (`api/server/services/`)
  - `AppService`, `AuthService`, `ModelService`, `PermissionService`, `ToolService`, `MCP/`
  - Endpoint services: `Endpoints/openAI/`, `Endpoints/google/`, `Endpoints/anthropic/`, etc.
  - File services: `Files/Local/`, `Files/S3/`, `Files/Firebase/`, `Files/Azure/`
- **Middleware:** Request processing (`api/server/middleware/`)
  - Authentication: JWT, local, LDAP, OAuth
  - Authorization: RBAC, resource permissions
  - Rate limiting, validation, security checks
- **Models:** Database models combining `data-schemas` with custom methods (`api/models/`)
- **Clients:** AI provider clients (`api/app/clients/`)
  - `BaseClient.js`, `OpenAIClient.js`, `AnthropicClient.js`, `GoogleClient.js`, etc.

**Authentication Flow:**
1. Multiple strategies via Passport.js (`api/strategies/`)
2. Supports: Local, JWT, LDAP, OAuth (Google/Facebook/GitHub/Discord/Apple), OIDC, SAML
3. Permission-based and role-based access control (RBAC)

**Agent System:**
- Agent models with versioning stored in MongoDB
- Permission system: VIEW, EDIT, DELETE, SHARED_GLOBAL bits
- Execution via `api/app/clients/agents/CustomAgent/`
- Agent routes: `/api/agents/*` with resource-level permissions

**MCP (Model Context Protocol):**
- Implementation in `packages/api/src/mcp/`
- `MCPManager` singleton manages server connections
- OAuth token handling with auto-reconnect
- User-specific and app-level connections
- Tool registration and execution

### Frontend Architecture

**Entry Point:** `client/src/main.jsx` → `App.jsx`

**State Management (Hybrid Approach):**
- **Recoil** (`client/src/store/`) - Application state atoms
  - Organized by feature: `artifacts/`, `agents/`, `endpoints/`, `user/`, `settings/`, `prompts/`, `mcp/`
- **React Query** (`librechat-data-provider/react-query`) - Server state
  - Data fetching, caching, mutations, optimistic updates
- **Jotai** (`@librechat/client` package) - Component-level state

**Routing:** React Router (`client/src/routes/`)
- Main chat: `/c/:conversationId?`
- Auth routes: `/login`, `/register`, `/forgot-password`, `/verify`
- Feature routes: `/agents`, `/search`, `/dashboard/*`
- Share: `/share/:shareId`

**Component Organization:** Feature-based (`client/src/components/`)
- `Chat/` - Main chat interface
- `Messages/` - Message rendering
- `Input/` - Chat input
- `Nav/` - Navigation sidebar
- `Agents/` - Agent marketplace
- `Prompts/` - Prompt library
- `Files/` - File management
- `Artifacts/` - Code artifacts
- `MCP/` - MCP server UI
- `ui/` - Shared UI components (Radix-based)

**Custom Hooks:** Extensive hook library (`client/src/hooks/`)
- Feature hooks: `Agents/`, `MCP/`, `Chat/`, `Files/`
- `useAuthContext`, `useNewConvo`, `useAppStartup`

### Configuration System

**librechat.yaml:**
- Comprehensive configuration file for endpoints, interface, file storage, etc.
- Example: `librechat.example.yaml`
- Loaded via `api/server/services/Config/loadCustomConfig.js`
- Supports local file or remote URL
- Zod validation and Redis caching

**Environment Variables:**
- `.env.example` contains 200+ configuration options
- Categories: Server, AI providers, auth, features, storage, search, security

**File Storage Strategies:**
- Configurable per file type (avatar, image, document)
- Supported: Local filesystem, AWS S3, Firebase Storage, Azure Blob Storage
- Implementation: `api/server/services/Files/{Local|S3|Firebase|Azure}/`

### Database

**MongoDB via Mongoose:**
- Schema definitions in `packages/data-schemas/src/schema/`
- Model methods in `api/models/`
- Key collections: User, Conversation, Message, File, Agent, Assistant, Prompt, Role, Transaction

**Meilisearch:**
- Full-text search for conversations and messages
- Container: `meilisearch` service in docker-compose

**Vector Database (PGVector):**
- PostgreSQL with pgvector extension
- Used for RAG (Retrieval-Augmented Generation)
- Container: `vectordb` service
- Accessed via `rag_api` microservice

### Key Integration Points

**AI Endpoints:**
- Client initialization pattern: `api/server/services/Endpoints/{provider}/initialize.js`
- Each provider has custom client extending `BaseClient`
- Token counting, streaming, conversation saving handled by base class

**File Handling:**
- Upload flow: Multer → validation → strategy selection → processing → storage → DB record
- File types: Images (resize/convert), documents (PDF parsing), code (sandboxing), audio (STT/TTS)
- Vector embeddings for semantic search

**Streaming:**
- Server-Sent Events (SSE) for AI responses
- WebSocket support for real-time updates
- Stream handling in `BaseClient` with generator functions

## Development Workflow

### Making Changes

1. **Backend Changes:**
   - Edit files in `api/` directory
   - Server auto-restarts with nodemon in dev mode
   - Check logs in `logs/` directory or console

2. **Frontend Changes:**
   - Edit files in `client/src/`
   - Vite HMR provides instant updates
   - Build shared packages if modifying them:
     ```bash
     npm run build:data-provider  # If changing data-provider
     npm run build:api            # If changing @librechat/api
     ```

3. **Shared Package Changes:**
   - Edit in `packages/{package-name}/src/`
   - Rebuild the package: `npm run build:{package-name}`
   - Restart dependent services (frontend dev server auto-reloads)

### Testing Strategy

- **Unit Tests:** Jest for both frontend and backend
- **Integration Tests:** API tests in `api/**/*.spec.js`
- **E2E Tests:** Playwright tests in `e2e/`
- Run tests before committing significant changes

### Docker Development

Default docker-compose includes:
- `api` - LibreChat application (port 3080)
- `mongodb` - Database (port 27017)
- `meilisearch` - Search engine (port 7700)
- `vectordb` - PGVector database
- `rag_api` - RAG API service

Override in `docker-compose.override.yml` for custom configurations.

## Important Patterns & Conventions

### API Route Pattern
```javascript
// api/server/routes/{resource}/index.js
router.get('/', middleware1, middleware2, controller.list);
router.post('/', validate, authorize, controller.create);
router.get('/:id', checkPermission, controller.get);
```

### Service Pattern
```javascript
// api/server/services/{Service}/index.js
class ServiceName {
  async method(params) {
    // Business logic
    // No direct DB access - use models
    return result;
  }
}
```

### React Component Pattern
```javascript
// client/src/components/{Feature}/{Component}.tsx
import { useRecoilState } from 'recoil';
import { useQuery } from '@tanstack/react-query';

function Component() {
  const [state, setState] = useRecoilState(atom);
  const { data } = useQuery({ ... });

  return <UI />;
}
```

### Permission Checks
- Middleware: `requirePermission(resource, permission)` in routes
- Service level: `PermissionService.checkPermission(user, resource, permission)`
- Permission bits: `VIEW`, `EDIT`, `DELETE`, `SHARED_GLOBAL`

### Error Handling
- Backend: Custom error classes, middleware catches and formats
- Frontend: `ApiErrorBoundaryProvider` catches API errors
- Toast notifications for user-facing errors

## Notes for Development

### Adding New AI Endpoints
1. Create client in `api/app/clients/`
2. Add initialization service in `api/server/services/Endpoints/{provider}/`
3. Add route handling in `api/server/routes/endpoints/`
4. Update `librechat.yaml` schema for configuration
5. Add frontend selector in `client/src/components/Endpoints/`

### Adding New Features to Agents
1. Update agent schema in `packages/data-schemas/src/schema/agentSchema.js`
2. Modify agent routes in `api/server/routes/agents/`
3. Update agent execution in `api/app/clients/agents/CustomAgent/`
4. Add UI components in `client/src/components/Agents/`

### Working with MCP Servers
- MCP configuration in `librechat.yaml` under `endpoints.agents.capabilities.mcp`
- Server management: `packages/api/src/mcp/MCPManager.ts`
- OAuth flows handled by `packages/api/src/mcp/oauth/`
- UI for server management in `client/src/components/MCP/`

### File Upload Customization
- Storage strategy configured per file type in `librechat.yaml`
- Extend storage services in `api/server/services/Files/`
- File processing hooks available for custom handling

### Database Migrations
- Migration scripts in `config/` directory
- Pattern: `migrate-{feature}.js` with `--dry-run` flag support
- Always test migrations with dry-run first
