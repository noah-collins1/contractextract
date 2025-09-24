# ContractExtract File Manifest

This document provides a comprehensive overview of every file in the ContractExtract project, including their purpose, status, and relationships.

## 📁 Root Directory Files

### 📖 Documentation Files
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `README.md` | Main project documentation with LibreChat integration guide | ✅ Active | Complete setup instructions, API docs, MCP tools |
| `CLAUDE.md` | Claude Code development guide and MCP integration runbook | ✅ Active | Technical setup instructions for development |
| `FILE_MANIFEST.md` | This file - comprehensive file directory | ✅ Active | Documents all project files and their purposes |
| `DEMO_STARTUP_CHECKLIST.md` | Quick demo startup guide | ✅ Active | Step-by-step demo preparation checklist |

### ⚙️ Environment Configuration
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `requirements-v2.txt` | Pydantic v2 environment dependencies (FastAPI + MCP) | ✅ Active | Main server environment |
| `requirements-v1.txt` | Pydantic v1 environment dependencies (LangExtract bridge) | ✅ Active | Optional bridge service |

## 🚀 Core Application Files

### 🌐 FastAPI Backend
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `app.py` | Main FastAPI application with MCP router | ✅ Active | Primary entry point, includes MCP endpoint |
| `db.py` | Database engine and session management | ✅ Active | PostgreSQL connection and SQLAlchemy setup |
| `bootstrap_db.py` | Database seeder - loads initial rule packs | ✅ Active | Creates tables and seeds initial data |

### 🗄️ Database Models & DTOs
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `models_rulepack.py` | SQLAlchemy model for rule_packs table | ✅ Active | Database schema definition |
| `rulepack_dtos.py` | Pydantic schemas for API data transfer | ✅ Active | API request/response models |
| `schemas.py` | Core Pydantic models (RuleSet, etc.) | ✅ Active | Business logic data models |

### 📊 Rule Pack Management
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `rulepack_repo.py` | Database CRUD operations for rule packs | ✅ Active | Repository pattern for data access |
| `rulepack_loader.py` | Load active rule packs for runtime evaluation | ✅ Active | Service layer for rule pack loading |
| `yaml_importer.py` | Import YAML rule definitions into database | ✅ Active | YAML → Database conversion |

### 🔍 Document Processing
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `ingest.py` | PDF text extraction utilities | ✅ Active | pdfplumber integration, text cleaning |
| `evaluator.py` | Core contract evaluation engine | ✅ Active | Rule application, report generation |
| `doc_type.py` | Document type detection via regex | ✅ Active | Auto-classify contracts by type |

### 🛠️ Utilities
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `main.py` | Batch runner for local PDF testing | ✅ Active | Development tool for testing |
| `telemetry.py` | Simple logging and telemetry hooks | ✅ Active | Monitoring and debugging |

## 🔌 MCP Integration

### 📡 MCP Server Components
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `mcp_server/__init__.py` | Python package marker | ✅ Active | Empty package initialization |
| `mcp_server/direct_mcp_endpoint.py` | JSON-RPC MCP protocol implementation | ✅ Active | **PRIMARY** - Direct FastAPI MCP endpoint |
| `mcp_server/tools.py` | 16 MCP tool functions | ✅ Active | **PRIMARY** - All MCP business logic |

### 🗑️ Obsolete MCP Files
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `mcp_server/server.py` | FastMCP mounting approach | ❌ Obsolete | Replaced by direct_mcp_endpoint.py |
| `mcp_server/alternative_server.py` | Alternative MCP implementation | ❌ Obsolete | Never fully implemented |

### 🌉 Bridge Integration
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `bridge_client.py` | HTTP client for v1 LangExtract bridge | ✅ Active | Optional v1 compatibility |
| `langextract_service.py` | v1 LangExtract compatibility service | ⚠️ Optional | Only needed for v1 bridge |

## 📁 LibreChat Integration

### 🔧 Configuration Files
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `librechat/librechat.yaml` | Complete LibreChat MCP configuration | ✅ Active | Copy to LibreChat root directory |
| `librechat/docker-compose.override.yml` | Docker networking setup | ✅ Active | Enables host.docker.internal access |
| `librechat/README.md` | LibreChat integration instructions | ✅ Active | Detailed setup and troubleshooting |

## 🎨 Frontend (React)

### 📦 Configuration & Build
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `front/package.json` | Frontend dependencies and scripts | ✅ Active | React, Vite, TypeScript setup |
| `front/vite.config.ts` | Vite bundler configuration | ✅ Active | Development server, build settings |
| `front/tsconfig.json` | TypeScript compiler configuration | ✅ Active | Type checking settings |
| `front/tsconfig.app.json` | Application-specific TS config | ✅ Active | App build configuration |
| `front/tsconfig.node.json` | Node.js-specific TS config | ✅ Active | Node utilities configuration |
| `front/eslint.config.js` | ESLint linting configuration | ✅ Active | Code quality rules |
| `front/.gitignore` | Frontend Git ignore rules | ✅ Active | Node modules, build artifacts |

### 🚀 Entry Points
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `front/index.html` | HTML entry point for React app | ✅ Active | Main HTML template |
| `front/src/main.tsx` | React application entry point | ✅ Active | App initialization |
| `front/src/App.tsx` | Main React component with routing | ✅ Active | Application router and layout |

### 🧩 React Components
| Directory | Purpose | Status | Notes |
|-----------|---------|--------|-------|
| `front/src/components/` | Reusable React components | ✅ Active | Navbar, FileRow, ReportCard, etc. |
| `front/src/pages/` | Page-level components | ✅ Active | Dashboard, Upload, Documents, RulePacks |
| `front/src/api/` | Axios API client and DTOs | ✅ Active | Backend API integration |

### 🎨 Assets & Styling
| Directory/File | Purpose | Status | Notes |
|----------------|---------|--------|-------|
| `front/public/` | Static assets (favicon, images) | ✅ Active | Public web assets |
| `front/src/theme.css` | Global CSS theme | ✅ Active | Navy blue/Volaris styling |

## 📄 Data & Output Directories

### 📊 Processing Directories
| Directory | Purpose | Status | Notes |
|-----------|---------|--------|-------|
| `data/` | Test PDF files for batch processing | ✅ Active | Sample contracts for testing |
| `outputs/` | Generated reports and analysis results | ✅ Active | Markdown/JSON reports, MCP demo results |
| `outputs/mcp_demo/` | MCP tool analysis outputs | ✅ Active | Created by MCP document analysis |

### 📋 Configuration Data
| Directory | Purpose | Status | Notes |
|-----------|---------|--------|-------|
| `rules_packs/` | YAML rule pack definitions | ✅ Active | Source YAML files for rule packs |

### 🗂️ Legacy Code
| Directory | Purpose | Status | Notes |
|-----------|---------|--------|-------|
| `archive/` | Legacy rule evaluation code | ⚠️ Archive | Old implementations, kept for reference |

## 🔒 Environment & Security

### 🔐 Sensitive Files (Not in Repo)
| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `.env` | Environment variables | 🚫 Private | Database URLs, API keys |
| `.env.local` | Local development overrides | 🚫 Private | Developer-specific settings |

### 🗃️ Virtual Environments (Not in Repo)
| Directory | Purpose | Status | Notes |
|-----------|---------|--------|-------|
| `.venv-v2/` | Pydantic v2 environment | 🚫 Local | FastAPI + MCP server environment |
| `.venv-v1/` | Pydantic v1 environment | 🚫 Local | Optional LangExtract bridge environment |
| `.venv/` | Legacy environment | ⚠️ Legacy | May contain old dependencies |

### 🗄️ Generated/Cache Directories (Not in Repo)
| Directory | Purpose | Status | Notes |
|-----------|---------|--------|-------|
| `__pycache__/` | Python bytecode cache | 🚫 Cache | Auto-generated Python cache |
| `mcp_server/__pycache__/` | MCP module cache | 🚫 Cache | Auto-generated cache |
| `archive/__pycache__/` | Archive module cache | 🚫 Cache | Auto-generated cache |
| `front/node_modules/` | Node.js dependencies | 🚫 Local | npm/yarn installed packages |
| `front/dist/` | Frontend build output | 🚫 Generated | Production build artifacts |

## 🏗️ Development & IDE Files

### 💡 IDE Configuration
| Directory/File | Purpose | Status | Notes |
|----------------|---------|--------|-------|
| `.idea/` | PyCharm/IntelliJ IDE settings | 🚫 Local | IDE-specific configuration |
| `.idea/workspace.xml` | IDE workspace layout | 🚫 Local | Window and tool configuration |

## 📊 File Status Legend

| Symbol | Status | Description |
|--------|--------|-------------|
| ✅ | Active | Currently used and maintained |
| ⚠️ | Optional/Archive | Used conditionally or archived |
| ❌ | Obsolete | No longer used, safe to remove |
| 🚫 | Private/Local | Not tracked in Git |

## 🎯 Critical Files for LibreChat Integration

### **Must Have (Core Functionality):**
1. `app.py` - Main FastAPI server
2. `mcp_server/direct_mcp_endpoint.py` - MCP protocol handler
3. `mcp_server/tools.py` - MCP tool implementations
4. `requirements-v2.txt` - Dependencies
5. `librechat/librechat.yaml` - LibreChat configuration

### **Database Required:**
1. `db.py` - Database connection
2. `models_rulepack.py` - Database schema
3. `bootstrap_db.py` - Initial data
4. `rulepack_*.py` - Rule pack management

### **Document Processing:**
1. `ingest.py` - PDF extraction
2. `evaluator.py` - Analysis engine
3. `doc_type.py` - Type detection

### **Optional but Recommended:**
1. `bridge_client.py` - v1 compatibility
2. `requirements-v1.txt` - Bridge dependencies
3. `librechat/docker-compose.override.yml` - Docker networking

## 🚀 Quick Start File Checklist

For a minimal working LibreChat integration:

**✅ Copy to LibreChat:**
- [ ] `librechat/librechat.yaml`
- [ ] `librechat/docker-compose.override.yml`

**✅ Environment Setup:**
- [ ] Install `requirements-v2.txt` in `.venv-v2`
- [ ] Run `bootstrap_db.py` to seed database

**✅ Start Services:**
- [ ] `uvicorn app:app --port 8000` (ContractExtract)
- [ ] `docker-compose up -d` (LibreChat)

**✅ Test MCP Integration:**
- [ ] Verify 16 tools available in LibreChat
- [ ] Test `get_system_info` tool call
- [ ] Test `list_active_rulepacks` tool call

This completes the comprehensive file manifest for the ContractExtract project.