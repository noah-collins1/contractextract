# ContractExtract - Pure MCP Contract Analysis System

A **pure MCP (Model Context Protocol) server** for AI-powered contract analysis, designed for seamless **LibreChat integration**. The system ingests PDFs, runs configurable rule-based compliance pipelines, and outputs detailed compliance reports in Markdown and JSON. Rules are stored as **versioned YAML "rule packs"** in PostgreSQL.

🔥 **Phase 4 Architecture**: Consolidated from 23 files to **5 core modules** with **pure stdio MCP protocol** - no HTTP overhead, optimal LibreChat performance!

---

## 📚 Table of Contents

### Getting Started
- [✨ Key Features](#-key-features) - Core capabilities and what makes ContractExtract unique
- [🏗 Architecture Overview](#-architecture-overview) - System design and pure MCP integration
- [🚀 Quick Start Guide](#-quick-start-guide) - Get running in 5 minutes
- [📋 Documentation Index](#-documentation-index) - Links to all documentation files

### Core Concepts
- [🗄 Database Schema](#-database-schema) - PostgreSQL rule pack storage
- [📄 YAML Rule Pack Schema](#-yaml-rule-pack-schema-v10) - Rule pack configuration format
- [🔌 MCP Tools Reference](#-mcp-tools-16-available) - Available MCP tools and their usage

### Development
- [🛠 Development Commands](#-development-commands) - Common development tasks
- [🔧 Configuration](#-configuration) - Environment and system configuration
- [🆘 Troubleshooting](#-troubleshooting) - Common issues and solutions
- [📊 API Endpoints](#-api-endpoints) - REST API reference (legacy support)

### Project Information
- [🛣 Roadmap](#-roadmap) - Future plans and upcoming features
- [👥 Team](#-team) - Project contributors
- [🔗 Related Documentation](#-related-documentation) - Additional resources

---

## ✨ Key Features

### Pure MCP Architecture (Phase 4)
- **Stdio protocol integration** - Direct process communication with LibreChat
- **5 consolidated core modules** - Simplified from 23 files for easier maintenance
- **16 comprehensive MCP tools** - Complete rule pack lifecycle + document analysis
- **Zero HTTP overhead** - Pure process communication for optimal performance
- **Single unified environment** - Pydantic v2 only, no environment switching

### Contract Analysis Engine
- **PDF ingestion** via [pdfplumber](https://github.com/jsvine/pdfplumber)
- **Document type auto-detection** (regex matching against `doc_type_names`)
- **Rule-based evaluation pipeline**:
  - Liability caps and contract value thresholds
  - Fraud clause detection with liability assignment
  - Jurisdiction allowlist compliance
  - Extensible via YAML configuration
- **Structured outputs**: JSON + **Markdown reports** with citations
- **Markdown report integration**: Full reports returned in MCP responses

### Database & Rule Management
- **Versioned rule packs**: draft → active → deprecated lifecycle
- **PostgreSQL storage** with full CRUD operations
- **YAML-based configuration** with schema validation
- **8 pre-built rule packs** for common contract types

---

## 🏗 Architecture Overview

### Pure MCP System Design

```
┌─────────────────────────────────┐
│        LibreChat               │
│  ┌─────────────────────────────┐│
│  │    MCP Client               ││
│  │  (stdio protocol)           ││
│  └─────────────────────────────┘│
└─────────────┬───────────────────┘
              │ stdio pipes
┌─────────────▼───────────────────┐
│     ContractExtract             │
│     mcp_server.py               │
│                                 │
│  ┌─────────────┐ ┌─────────────┐│
│  │16 MCP Tools │ │Consolidated ││
│  │             │ │5 Core Files ││
│  │• Rule Mgmt  │ │             ││
│  │• Doc Analysis│ │• Unified    ││
│  │• Utilities  │ │  Pydantic v2││
│  └─────────────┘ │• LangExtract││
│                  │  1.0.9      ││
│  ┌─────────────┐ └─────────────┘│
│  │PostgreSQL   │                │
│  │Rule Packs   │                │
│  └─────────────┘                │
└─────────────────────────────────┘
```

### Core File Structure (Consolidated - Phase 4)

```
contractextract/
├── 📚 Documentation (Enhanced)
│   ├── README.md                    # This file - comprehensive guide
│   ├── CLAUDE.md                    # Development guide + MCP setup
│   ├── CHANGELOG.md                 # Version history + Phase 4 updates
│   ├── FILE_MANIFEST.md             # Complete file directory
│   ├── DEMO_STARTUP_CHECKLIST.md    # Quick startup guide
│   └── TEST_PLAN.md                 # Testing documentation
│
├── 🚀 Core Application (5 Consolidated Files)
│   ├── mcp_server.py                # Pure stdio MCP server (959 lines)
│   ├── infrastructure.py            # Config/DB/schemas/telemetry (267 lines)
│   ├── contract_analyzer.py         # Analysis engine + LLM (590 lines)
│   ├── document_analysis.py         # Document processing pipeline (514 lines)
│   └── rulepack_manager.py          # Rule pack data access layer (313 lines)
│
├── ⚙️ Configuration
│   ├── requirements.txt             # Unified Pydantic v2 dependencies
│   ├── librechat_mcp_config.yaml    # LibreChat stdio MCP configuration
│   └── llm.yaml                     # LLM provider settings
│
├── 📋 Data & Rules
│   ├── rules_packs/                 # YAML rule definitions (8 files)
│   │   ├── _TEMPLATE.yml            # Standard schema template
│   │   ├── strategic_alliance.yml   # Reference implementation
│   │   ├── employment.yml           # Employment contracts
│   │   ├── noncompete.yml           # Non-compete agreements
│   │   ├── ip_agreement.yml         # IP assignment rules
│   │   ├── joint_venture.yml        # Joint venture rules
│   │   ├── promotion.yml            # Marketing agreements
│   │   └── servicing.yml            # Service agreements
│   ├── data/                        # Test PDF documents
│   └── outputs/                     # Generated analysis reports
│
├── 🗂 Archive & Reference
│   ├── archive/                     # Legacy evaluation code
│   ├── stash/                       # Development backups
│   └── mcp_server_fastmcp_backup.py # FastMCP backup (pre-Phase 4)
│
└── 🐍 Environment
    ├── .venv/                       # Unified Python 3.11 + Pydantic v2
    └── phase4_backup_inventory.txt  # Phase 4 file inventory
```

### Key Architecture Changes (Phase 4)

**Consolidated:** 23 files → 5 core modules
- `app.py`, `db.py`, `models_rulepack.py`, `schemas.py`, `telemetry.py`, `settings.py` → **`infrastructure.py`**
- `evaluator.py`, `llm_factory.py`, `llm_provider.py`, `citation_mapper.py` → **`contract_analyzer.py`**
- `ingest.py`, `doc_type.py`, `document_classifier.py` → **`document_analysis.py`**
- `rulepack_repo.py`, `rulepack_loader.py`, `rulepack_dtos.py`, `yaml_importer.py` → **`rulepack_manager.py`**
- `mcp_server/` directory (6 files) → **`mcp_server.py`** (single file, pure stdio)

**Removed:**
- ❌ FastAPI + HTTP server (replaced by pure MCP)
- ❌ React frontend (LibreChat provides UI)
- ❌ Dual Pydantic environments (unified on v2)
- ❌ HTTP MCP protocol (replaced by stdio)
- ❌ Bridge services (no longer needed)

---

## 🗄 Database Schema

**Table: `rule_packs`** (PostgreSQL)

| Column                   | Type        | Description                                   |
|---------------------------|-------------|-----------------------------------------------|
| `id`                     | text        | Stable identifier (e.g. `strategic_alliance`) |
| `version`                | int         | Version number (composite PK with `id`)       |
| `status`                 | enum        | `draft` \| `active` \| `deprecated`         |
| `schema_version`         | text        | Rule pack schema version (default: `"1.0"`)   |
| `doc_type_names`         | jsonb       | Document type names for auto-detection        |
| `ruleset_json`           | jsonb       | Structured rules (jurisdiction, liability, etc.) |
| `rules_json`             | jsonb       | Extended rules (optional, extensible)         |
| `llm_prompt`             | text        | LLM prompt for rationale generation           |
| `llm_examples_json`      | jsonb       | Examples for LLM few-shot learning           |
| `extensions_json`        | jsonb       | Custom extensions (optional)                  |
| `extensions_schema_json` | jsonb       | Extensions validation schema                  |
| `raw_yaml`               | text        | Original YAML for round-trip editing         |
| `notes`                  | text        | Human-readable notes                          |
| `created_by`             | text        | Author/creator identifier                     |
| `created_at`             | timestamptz | Creation timestamp                            |
| `updated_at`             | timestamptz | Last modification timestamp                   |

---

## 📄 YAML Rule Pack Schema (v1.0)

All rule packs conform to **Schema Version 1.0** for compatibility.

### Required Fields

```yaml
id: "unique_identifier_v1"
schema_version: "1.0"
doc_type_names:
  - "Contract Type Name"
jurisdiction_allowlist:
  - "United States"
liability_cap:
  max_cap_amount: 1000000.0
  max_cap_multiplier: 1.0
contract:
  max_contract_value: 5000000.0
fraud:
  require_fraud_clause: true
  require_liability_on_other_party: true
prompt: |
  LLM analysis prompt...
examples:
  - text: "Sample text"
    extractions: [...]
```

### Optional Fields

```yaml
rules: []                    # Extended domain rules
notes: "Description"         # Documentation
extensions: {}               # Custom fields
extensions_schema: {}        # Validation schema
```

### Available Rule Packs

- `strategic_alliance.yml` - Partnerships, liability limits, fraud protection
- `employment.yml` - Employment contracts, termination, classification
- `noncompete.yml` - Non-compete agreements, duration, scope
- `ip_agreement.yml` - IP assignment, moral rights, license-back
- `joint_venture.yml` - Capital contributions, deadlock, exit
- `promotion.yml` - Marketing agreements, performance, renewals
- `servicing.yml` - Service agreements, SLAs, liability

---

## 🔌 MCP Tools (16 Available)

### Rule Pack Management (8 tools)
- **`list_all_rulepacks`** - List ALL rule packs (any status/version)
- **`list_active_rulepacks`** - List only active rule packs
- **`get_rulepack_details`** - Get detailed rule pack information
- **`get_rulepack_yaml`** - Retrieve raw YAML content
- **`list_rulepack_versions`** - List all versions for a rule pack
- **`create_rulepack_from_yaml`** - Create new rule packs from YAML
- **`update_rulepack_yaml`** - Edit draft rule packs
- **`publish_rulepack`** - Publish drafts to active status

### Rule Pack Lifecycle (2 tools)
- **`deprecate_rulepack`** - Deprecate active rule packs
- **`delete_rulepack`** - Delete rule packs (with safety checks)

### Document Analysis (2 tools)
- **`analyze_document`** - Full analysis with **markdown report** in response
- **`preview_document_analysis`** - Quick preview without file output

### Utilities (4 tools)
- **`generate_rulepack_template`** - Generate YAML template
- **`validate_rulepack_yaml`** - Validate YAML before import
- **`get_system_info`** - System status and diagnostics

---

## 🚀 Quick Start Guide

### Prerequisites (One-Time Setup)

1. **Python 3.11+** installed
2. **PostgreSQL** with `contractextract` database:
   ```sql
   CREATE DATABASE contractextract;
   ```
3. **LibreChat** installed (follow [LibreChat docs](https://docs.librechat.ai))

### Step 1: Setup Environment

```powershell
# Clone repository
cd C:\path\to\project

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies (unified Pydantic v2)
pip install -r requirements.txt
```

### Step 2: Initialize Database

```powershell
# Ensure .venv is activated
python infrastructure.py  # Creates tables
python rulepack_manager.py  # Seeds initial data (if needed)
```

### Step 3: Configure LibreChat

Create or update `librechat.yaml` in your LibreChat directory:

```yaml
mcpServers:
  contractextract:
    command: "python"
    args: ["mcp_server.py"]
    cwd: "C:\\path\\to\\langextract"
    initTimeout: 150000
    serverInstructions: true
```

### Step 4: Start LibreChat

```powershell
cd C:\path\to\LibreChat
docker-compose up -d
```

LibreChat will automatically spawn the ContractExtract MCP server!

### Step 5: Test Integration

In LibreChat chat interface:

1. **System Info:** `Get ContractExtract system information`
2. **List Packs:** `Show me all available rule packs`
3. **Analyze:** Upload a contract PDF and ask: `Analyze this contract`

---

## 🛠 Development Commands

### Run MCP Server Manually (Development)

```powershell
.\.venv\Scripts\Activate.ps1
python mcp_server.py
```

### Test Imports

```powershell
python -c "import mcp_server; print('MCP server ready')"
python -c "from infrastructure import init_db; init_db(); print('Database connected')"
python -c "from contract_analyzer import make_report; print('Analysis engine ready')"
```

### Validate Rule Packs

```powershell
# Test YAML schema compliance
python -c "from rulepack_manager import validate_yaml; validate_yaml('rules_packs/strategic_alliance.yml')"
```

---

## 🔧 Configuration

### Environment Variables

Create `.env` file (optional):

```bash
# Database (auto-detected if PostgreSQL on localhost)
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/contractextract

# LLM Configuration
ENABLE_LLM_EXPLANATIONS=1
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434

# Logging
CE_LOG_LEVEL=INFO
```

### LibreChat MCP Configuration

**Minimal** (`librechat.yaml`):
```yaml
mcpServers:
  contractextract:
    command: "python"
    args: ["mcp_server.py"]
    cwd: "C:\\Users\\username\\PycharmProjects\\langextract"
```

**Production** (Linux/Docker):
```yaml
mcpServers:
  contractextract:
    command: "/opt/contractextract/.venv/bin/python"
    args: ["mcp_server.py"]
    cwd: "/opt/contractextract"
    env:
      DATABASE_URL: "postgresql://user:pass@db:5432/contractextract"
```

---

## 🆘 Troubleshooting

### "MCP server failed to initialize"
1. Verify Python 3.11+ installed: `python --version`
2. Check dependencies: `pip list | grep mcp`
3. Test imports: `python -c "import mcp_server"`
4. Increase `initTimeout` in `librechat.yaml`

### "Database connection failed"
1. Start PostgreSQL service
2. Verify database exists: `psql -l | grep contractextract`
3. Test connection: `python -c "from infrastructure import init_db; init_db()"`

### "Import errors"
1. Activate environment: `.\.venv\Scripts\Activate.ps1`
2. Reinstall: `pip install -r requirements.txt`
3. Check Pydantic version: `python -c "import pydantic; print(pydantic.__version__)"` (should be 2.x)

### "LibreChat can't connect"
1. Check stdio protocol (not HTTP) in `librechat.yaml`
2. Verify absolute path in `cwd` setting
3. Check LibreChat can spawn Python processes
4. Enable debug logging: `CE_LOG_LEVEL=DEBUG`

---

## 📊 API Endpoints

*Note: Pure MCP architecture does not expose HTTP endpoints. Legacy REST API has been removed in Phase 4.*

For programmatic access, use the MCP tools via LibreChat integration.

---

## 🛣 Roadmap

### Completed (Phase 4 - Current)
- ✅ **Pure stdio MCP protocol** - Zero HTTP overhead
- ✅ **File consolidation** - 23 files → 5 core modules
- ✅ **Unified environment** - Single Pydantic v2 setup
- ✅ **Markdown report integration** - Full reports in MCP responses
- ✅ **Enhanced documentation** - Complete rewrite for new architecture

### Next (v1.3)
- [ ] Multi-language document support
- [ ] Enhanced citation highlighting with visual markers
- [ ] Export compliance dashboards
- [ ] Advanced LLM rationale generation

### Future (v2.0)
- [ ] Machine learning model integration
- [ ] Custom rule pack templates with GUI
- [ ] Advanced workflow automation
- [ ] Enterprise user management and audit logs

---

## 👥 Team

- **Lead Developer**: Noah Collins
- **Project Manager**: Trey Drake
- **Architecture**: Pure MCP + PostgreSQL + LibreChat

---

## 📋 Documentation Index

Comprehensive documentation for all aspects of ContractExtract:

### 📖 Core Documentation
| Document | Description | Audience |
|----------|-------------|----------|
| [README.md](./README.md) | **This file** - Complete system overview, quick start, MCP tools reference | All users |
| [CLAUDE.md](./CLAUDE.md) | Development guide for Claude Code with MCP setup, architecture details, deployment | Developers |
| [CHANGELOG.md](./CHANGELOG.md) | Version history, Phase 4 consolidation details, feature tracking | All users |

### 🚀 Getting Started
| Document | Description | Audience |
|----------|-------------|----------|
| [DEMO_STARTUP_CHECKLIST.md](./DEMO_STARTUP_CHECKLIST.md) | Quick 5-minute startup guide for demos and testing | New users, demos |
| [TEST_PLAN.md](./TEST_PLAN.md) | Comprehensive testing procedures and validation | QA, developers |

### 🗂 Reference
| Document | Description | Audience |
|----------|-------------|----------|
| [FILE_MANIFEST.md](./FILE_MANIFEST.md) | Complete file directory with purpose, status, and relationships | Developers, maintainers |
| [librechat_mcp_config.yaml](./librechat_mcp_config.yaml) | LibreChat MCP configuration examples and settings | Deployment, ops |

### 📁 External Resources
| Resource | Description | Link |
|----------|-------------|------|
| **MCP Protocol Spec** | Model Context Protocol documentation | [modelcontextprotocol.io](https://modelcontextprotocol.io/) |
| **LibreChat Docs** | LibreChat installation and configuration | [docs.librechat.ai](https://docs.librechat.ai/) |
| **LangExtract** | LLM-powered information extraction library | [GitHub](https://github.com/VarunBhaskaran/langextract) |

---

## 🔗 Related Documentation

- [CLAUDE.md](./CLAUDE.md) - Comprehensive development guide
- [CHANGELOG.md](./CHANGELOG.md) - Version history and updates
- [FILE_MANIFEST.md](./FILE_MANIFEST.md) - Complete file directory
- [MCP Protocol](https://modelcontextprotocol.io/) - Protocol specification

---

## 📄 License

This project is proprietary software developed for enterprise contract analysis applications.

---

**🚀 Pure MCP architecture - Optimized for LibreChat integration with zero HTTP overhead!**