# ContractExtract - AI-Powered Contract Analysis with LibreChat MCP Integration

A **FastAPI-based contract analysis service** with **React frontend** and **comprehensive LibreChat MCP (Model Context Protocol) integration**.

The system ingests PDFs, runs them through configurable rule-based compliance pipelines, and outputs detailed **compliance reports** in Markdown and JSON. Rules are stored as **versioned YAML "rule packs"** in PostgreSQL, enabling fully data-driven behavior with optional LLM rationales.

🔥 **NEW**: Complete LibreChat integration with **16 MCP tools** allowing LLMs to create, edit, and manage rule packs while analyzing contracts in real-time!

---

## ✨ Key Features

### Core Contract Analysis
- **PDF ingestion** via [pdfplumber](https://github.com/jsvine/pdfplumber)
- **Document type detection** (regex matching against `doc_type_names`)
- **Rule-based evaluation pipeline**:
  - Liability caps and limits
  - Contract value thresholds
  - Fraud clause detection
  - Jurisdiction allowlist compliance
  - Extensible via YAML configuration
- **Structured outputs**: JSON reports + Markdown summaries
- **Optional LLM rationales** for failed findings

### LibreChat MCP Integration (NEW!)
- **16 comprehensive MCP tools** for complete rule pack lifecycle management
- **Real-time rule pack creation/editing** via natural language
- **Document analysis directly in LibreChat** conversations
- **YAML template generation** for new rule packs
- **Validation and preview** capabilities
- **Dual environment support** (Pydantic v1/v2 compatibility)

### Database & API
- **Versioned rule packs**: draft → active → deprecated lifecycle
- **PostgreSQL storage** with full CRUD operations
- **REST API** with comprehensive Swagger UI (`/docs`)
- **Batch processing** for local PDF testing
- **React frontend** for rule pack management

---

## 🏗 Architecture Overview

### System Components

```
LibreChat (Docker)
    ↓ MCP Protocol (JSON-RPC)
ContractExtract FastAPI (.venv-v2, Pydantic v2)
    ↓ Database Queries
PostgreSQL (rule_packs table)
    ↓ Optional Bridge (HTTP)
LangExtract v1 Service (.venv-v1, Pydantic v1) [Optional]
```

### Directory Structure

```
contractextract/
├── README.md                    # This file
├── CLAUDE.md                    # Claude Code development guide
├── requirements-v1.txt          # Pydantic v1 environment dependencies
├── requirements-v2.txt          # Pydantic v2 environment dependencies
│
├── librechat/                   # 📁 LibreChat integration files
│   ├── librechat.yaml           # MCP server configuration
│   ├── docker-compose.override.yml # Docker networking setup
│   └── README.md                # Integration instructions
│
├── app.py                       # 🚀 Main FastAPI application
├── db.py                        # Database engine and session management
├── bootstrap_db.py              # Database seeder (loads initial rule packs)
├── models_rulepack.py           # SQLAlchemy model (rule_packs table)
├── rulepack_*.py                # Rule pack management (repo, loader, DTOs)
├── yaml_importer.py             # YAML → Database import logic
├── evaluator.py                 # Core contract evaluation engine
├── ingest.py                    # PDF text extraction utilities
├── doc_type.py                  # Document type detection
├── schemas.py                   # Core Pydantic models
├── main.py                      # Batch runner for local testing
│
├── mcp_server/                  # 🔌 MCP Integration
│   ├── __init__.py
│   ├── direct_mcp_endpoint.py   # JSON-RPC MCP protocol implementation
│   ├── tools.py                 # 16 MCP tool functions
│   ├── server.py                # [OBSOLETE] FastMCP mounting approach
│   └── alternative_server.py    # [OBSOLETE] Alternative implementation
│
├── bridge_client.py             # HTTP client for v1 LangExtract bridge
├── langextract_service.py       # [OPTIONAL] v1 compatibility service
│
├── front/                       # 🎨 React Frontend
│   ├── package.json             # Frontend dependencies
│   ├── vite.config.ts           # Vite bundler configuration
│   ├── src/                     # React components and pages
│   └── public/                  # Static assets
│
├── data/                        # 📄 Test PDFs for batch processing
├── outputs/                     # 📊 Generated reports and analysis results
├── rules_packs/                 # 📋 YAML rule pack definitions
│   ├── _TEMPLATE.yml             # Standard schema template
│   ├── strategic_alliance.yml    # Reference implementation
│   ├── employment.yml            # Employment contract rules
│   ├── noncompete.yml            # Non-compete agreement rules
│   ├── ip_agreement.yml          # IP assignment rules
│   ├── joint_venture.yml         # Joint venture rules
│   ├── promotion.yml             # Marketing promotion rules
│   └── servicing.yml             # Service agreement rules
├── validate_yaml_rulepacks.py    # YAML validation script
└── archive/                     # 🗂 Legacy evaluation code
```

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

## 📋 YAML Rule Pack Schema (v1.0)

ContractExtract uses a **standardized YAML schema** for rule pack definitions. All rule packs must conform to **Schema Version 1.0** for compatibility and consistency.

### Standard Schema Structure

#### **Required Fields** (Must be present in every rule pack):

```yaml
id: "unique_identifier_v1"                    # Unique rule pack identifier
schema_version: "1.0"                         # Schema compatibility version
doc_type_names:                               # Document types for auto-detection
  - "Primary Document Type"
  - "Alternative Document Type"
jurisdiction_allowlist:                       # Allowed governing law jurisdictions
  - "United States"
  - "Canada"
liability_cap:                                # Liability cap policy
  max_cap_amount: 1000000.0                   # Max absolute cap (null = no limit)
  max_cap_multiplier: 1.0                     # Max cap as contract multiplier
contract:                                     # Contract value constraints
  max_contract_value: 5000000.0               # Max total contract value
fraud:                                        # Fraud clause requirements
  require_fraud_clause: true                  # Whether fraud clause required
  require_liability_on_other_party: true      # Whether fraud liability must be assigned
prompt: |                                     # Structured LLM extraction prompt
  Standardized prompt format for extractions...
examples:                                     # Training examples
  - text: "Sample contract text"
    extractions:
      - label: "extraction_type"
        span: "relevant text span"
        attributes: { key: value }
```

#### **Optional Fields** (May be present):

```yaml
rules:                                        # Extended domain-specific rules
  - id: custom_rule_id
    type: domain.rule_type
    params:
      custom_param: true
notes: "Description and metadata"             # Documentation
extensions:                                   # Custom fields
  custom_field: "value"
extensions_schema:                            # Schema for extensions validation
  type: "object"
  properties:
    custom_field:
      type: "string"
```

### Schema Benefits

- **🔗 Interoperability**: All rule packs work with the same import/export system
- **🛠 Maintainability**: Easy to update multiple rule packs with schema changes
- **📈 Extensibility**: `rules` and `extensions` sections allow domain-specific customizations
- **✅ Quality Assurance**: Automated validation prevents malformed rule packs

### Validation

Use the included validation script to ensure YAML compliance:

```powershell
python validate_yaml_rulepacks.py
```

**Validation Features:**
- **Required field checking**: Ensures all mandatory fields are present
- **Type validation**: Verifies correct data types (strings, lists, dicts)
- **Structure constraints**: Validates nested field requirements
- **Schema version compatibility**: Checks against declared schema version

### Available Rule Packs

- **`strategic_alliance.yml`** - Strategic partnerships, liability limits, fraud protection
- **`employment.yml`** - Employment contracts, termination, worker classification
- **`noncompete.yml`** - Non-compete agreements, duration, geographic scope
- **`ip_agreement.yml`** - IP assignment, moral rights, license-back provisions
- **`joint_venture.yml`** - Capital contributions, deadlock resolution, exit strategies
- **`promotion.yml`** - Marketing agreements, performance metrics, renewals
- **`servicing.yml`** - Service agreements, SLAs, liability allocation

---

## 🔌 LibreChat MCP Tools (16 Available)

### Rule Pack Management
- **`list_all_rulepacks`** - List ALL rule packs (any status/version)
- **`list_active_rulepacks`** - List only active rule packs for runtime
- **`get_rulepack_details`** - Get detailed rule pack information
- **`get_rulepack_yaml`** - Retrieve raw YAML content
- **`list_rulepack_versions`** - List all versions for a rule pack ID

### Rule Pack Creation & Editing (LLM-Powered!)
- **`create_rulepack_from_yaml`** - Create new rule packs from YAML
- **`update_rulepack_yaml`** - Edit draft rule packs
- **`publish_rulepack`** - Publish drafts to make them active
- **`deprecate_rulepack`** - Deprecate active rule packs
- **`delete_rulepack`** - Delete rule packs (with safety controls)

### Document Analysis
- **`analyze_document`** - Comprehensive document analysis with citations
- **`preview_document_analysis`** - Quick preview without saving files

### Utilities & Development
- **`generate_rulepack_template`** - Generate YAML templates for new packs
- **`validate_rulepack_yaml`** - Validate YAML before creating/updating
- **`get_system_info`** - System status and monitoring information

### Legacy Compatibility
- **`list_rulepacks`**, **`get_rulepack`**, **`analyze`** - Backward compatibility

---

## 🚀 LibreChat Startup Instructions

### Prerequisites (One-Time Setup)

1. **Install Python 3.11**
2. **Install PostgreSQL** and create `contractextract` database:
   ```sql
   CREATE DATABASE contractextract;
   ```
3. **Install LibreChat** (follow their documentation)
4. **Clone this repository**

### Step 1: Create Virtual Environments

```powershell
# Navigate to project directory
cd C:\path\to\contractextract

# Create Pydantic v2 environment (FastAPI + MCP)
python -m venv .venv-v2
.\.venv-v2\Scripts\Activate.ps1
pip install -r requirements-v2.txt

# Create Pydantic v1 environment (optional, for LangExtract bridge)
python -m venv .venv-v1
.\.venv-v1\Scripts\Activate.ps1
pip install -r requirements-v1.txt
```

### Step 2: Configure LibreChat

Copy configuration files from the `librechat/` folder to your LibreChat installation:

```powershell
# Copy LibreChat configuration files
copy librechat\librechat.yaml C:\path\to\your\LibreChat\
copy librechat\docker-compose.override.yml C:\path\to\your\LibreChat\
```

### Step 3: Initialize Database

```powershell
# Activate v2 environment
.\.venv-v2\Scripts\Activate.ps1

# Seed database with initial rule packs
python bootstrap_db.py
```

### Step 4: Start ContractExtract Server

```powershell
# Ensure v2 environment is active
.\.venv-v2\Scripts\Activate.ps1

# Start FastAPI server with MCP integration
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

**✅ Verify:**
- Server logs show: `"All MCP tools registered successfully - 16 total tools"`
- FastAPI docs accessible: http://127.0.0.1:8000/docs
- MCP endpoint responds: `curl -X POST http://localhost:8000/mcp -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}'`

### Step 5: Start LibreChat

```powershell
# Navigate to LibreChat directory
cd C:\path\to\your\LibreChat

# Start LibreChat with Docker Compose
docker-compose up -d
```

**✅ Verify:**
- LibreChat accessible: http://localhost:3080
- No MCP initialization errors in logs
- ContractExtract tools appear in chat interface

### Step 6: Test MCP Integration

In LibreChat chat interface:

1. **Test Connection:** `Get system information about ContractExtract`
2. **List Rule Packs:** `Show me all available rule packs`
3. **Analyze Contract:** `Analyze this contract text: "Service Agreement between Company A and B, value $50,000, governed by California law"`
4. **Create Rule Pack:** `Generate a template for a new 'vendor_agreement' rule pack`

---

## 🛠 Development Commands

### FastAPI Server (Pydantic v2)
```powershell
.\.venv-v2\Scripts\Activate.ps1
uvicorn app:app --reload --port 8000
```

### Optional LangExtract Bridge (Pydantic v1)
```powershell
.\.venv-v1\Scripts\Activate.ps1
uvicorn langextract_service:app --port 8091 --reload
```

### React Frontend
```powershell
cd front
npm install
npm run dev  # http://localhost:5173
```

### Batch Processing
```powershell
.\.venv-v2\Scripts\Activate.ps1
python main.py  # Processes PDFs in data/ folder
```

---

## 🔧 Configuration Files

### Environment Variables

**Required:**
- `DATABASE_URL` - PostgreSQL connection string (default: `postgresql+psycopg2://postgres:1219@localhost:5432/contractextract`)

**Optional:**
- `USE_V1_BRIDGE=1` - Enable LangExtract v1 bridge integration
- `ENABLE_LLM_EXPLANATIONS=1` - Enable LLM rationales for failed findings
- `LLM_PROVIDER` - LLM provider configuration (default: "ollama")
- `CE_MAX_WORKERS` - Document-level parallelism (default: 1)
- `CE_CHUNK_TARGET` - Target chunk size in characters (default: 9000)

### LibreChat Integration

The `librechat/` folder contains:

- **`librechat.yaml`** - Complete MCP server configuration
- **`docker-compose.override.yml`** - Docker networking setup for host connectivity
- **`README.md`** - Detailed integration instructions

---

## 🆘 Troubleshooting

### "MCP server failed to initialize"
1. Verify FastAPI server running on port 8000
2. Check LibreChat uses correct URL (`localhost` vs `host.docker.internal`)
3. Confirm MCP tools registered in server logs
4. Increase `initTimeout` in librechat.yaml

### "Port already in use"
```powershell
# Kill existing processes
Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Stop-Process -Force
# Or change ports and update configuration
```

### "Database connection failed"
1. Start PostgreSQL service
2. Verify `contractextract` database exists
3. Check `DATABASE_URL` environment variable

### "Import errors"
1. Ensure correct virtual environment activated
2. Verify requirements installed: `pip list`
3. Check Python version: `python --version` (should be 3.11)

---

## 📊 API Endpoints

### Rule Pack Management
- `GET /rule-packs/all` - List all rule packs
- `GET /rule-packs/{id}` - List versions for rule pack
- `GET /rule-packs/{id}/{version}` - Get rule pack details
- `GET /rule-packs/{id}/{version}/yaml` - Download YAML
- `POST /rule-packs/import-yaml` - Import YAML as draft
- `POST /rule-packs/upload-yaml` - Upload YAML file
- `POST /rule-packs/{id}/{version}:publish` - Publish draft
- `POST /rule-packs/{id}/{version}:deprecate` - Deprecate pack
- `PUT /rule-packs/{id}/{version}` - Edit draft pack
- `DELETE /rule-packs/{id}/{version}` - Delete pack

### Document Analysis
- `POST /preview-run` - Upload PDF for analysis

### MCP Protocol
- `POST /mcp` - JSON-RPC MCP endpoint (used by LibreChat)

---

## 🎯 Use Cases & Demo Scenarios

### Basic Contract Analysis
1. Upload contract PDF via LibreChat
2. System auto-detects document type
3. Runs compliance checks against active rule packs
4. Returns detailed findings with citations

### Rule Pack Development
1. Generate template: `Create a new rule pack for vendor agreements`
2. Edit YAML through conversation: `Add liability cap requirement of $1M minimum`
3. Validate and publish: `Publish this rule pack as version 1`
4. Test immediately: `Analyze a contract with this new rule pack`

### Compliance Monitoring
1. Analyze multiple contracts in batch
2. Generate compliance reports
3. Track violations across document types
4. Monitor rule pack effectiveness

---

## 🛣 Roadmap

### Immediate (v1.3)
- [ ] Enhanced LLM rationale generation
- [ ] Multi-language document support
- [ ] Advanced citation highlighting
- [ ] Export compliance dashboards

### Medium-term (v2.0)
- [ ] Machine learning model integration
- [ ] Custom rule pack templates
- [ ] Advanced workflow automation
- [ ] Enterprise user management

### Long-term (v3.0)
- [ ] Real-time collaboration features
- [ ] Advanced analytics and reporting
- [ ] Integration with legal databases
- [ ] AI-powered contract drafting assistance

---

## 👥 Team

- **Lead Developer**: Noah Collins
- **Project Manager**: Trey Drake
- **Architecture**: FastAPI + React + PostgreSQL + LibreChat MCP

---

## 📄 License

This project is proprietary software developed for enterprise contract analysis applications.

---

## 🔗 Related Documentation

- [CLAUDE.md](./CLAUDE.md) - Development guide for Claude Code
- [LibreChat Integration Guide](./librechat/README.md) - Detailed integration instructions
- [MCP Protocol Documentation](https://modelcontextprotocol.io/) - Model Context Protocol specification

---

**🚀 Ready to revolutionize contract analysis with AI-powered LibreChat integration!**