# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend (Python FastAPI) - Pydantic v2 Environment
```bash
# Activate the v2 environment
.\.venv-v2\Scripts\Activate.ps1

# Install dependencies (if needed)
pip install -r requirements-v2.txt

# Initialize database tables
python bootstrap_db.py

# Run the API server with MCP integration
uvicorn app:app --reload --port 8000

# Run batch processing on PDFs in data/ folder
python main.py

# Validate YAML rule packs
python validate_yaml_rulepacks.py
```

### Frontend (React/TypeScript)
```bash
# Navigate to frontend directory
cd front

# Install dependencies
npm install

# Start development server
npm run dev        # Runs at http://localhost:5173

# Build for production
npm run build

# Preview production build
npm run preview
```

## Architecture Overview

This is a **contract analysis and compliance checking system** built with FastAPI backend and React frontend.

### Core Data Flow
1. **Rule Packs**: YAML-based compliance rules stored in PostgreSQL with versioning (draft → active → deprecated)
2. **Document Processing**: PDFs ingested via pdfplumber, text extracted and chunked by pages
3. **Type Detection**: Documents auto-classified by regex matching against `doc_type_names` in rule packs
4. **Evaluation Pipeline**: Text processed through configurable rules (jurisdiction, liability caps, contract values, fraud clauses)
5. **Report Generation**: Structured findings output as Markdown and JSON with citations

### Key Architectural Components

**Database Layer** (`db.py`, `models_rulepack.py`):
- PostgreSQL with SQLAlchemy ORM
- Single `rule_packs` table with versioned YAML rule configurations
- Connection string: `postgresql+psycopg2://postgres:1219@localhost:5432/contractextract`

**Rule Management** (`rulepack_*.py`):
- `rulepack_repo.py`: Database CRUD operations
- `rulepack_loader.py`: Load active packs for runtime evaluation
- `yaml_importer.py`: Import YAML rule definitions into database
- `rulepack_dtos.py`: Pydantic schemas for API data transfer

**Document Processing** (`ingest.py`, `main.py`):
- PDF text extraction with form-feed page break preservation
- Chunking strategy: merge adjacent pages up to ~9000 chars (configurable via `CE_CHUNK_TARGET`)
- Batch processing with optional multiprocessing (`CE_MAX_WORKERS`)

**Evaluation Engine** (`evaluator.py`, `schemas.py`):
- Rule-based compliance checking with extensible finding types
- Citation tracking with character-level positioning
- Optional LLM rationale generation (enabled via `ENABLE_LLM_EXPLANATIONS=1`)
- Monetary context guards to avoid false positives on share counts

**LLM Integration** (`llm_factory.py`, `llm_provider.py`):
- Provider abstraction supporting completion, chat, and extraction APIs
- Default configuration for local Ollama deployment
- Configurable via `llm.yaml` and `LLM_PROVIDER` environment variable

**API Layer** (`app.py`):
- REST endpoints for rule pack lifecycle management
- File upload and preview processing endpoints
- CORS enabled for local frontend development
- Auto-generates Swagger documentation at `/docs`

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `ENABLE_LLM_EXPLANATIONS`: Enable LLM rationales for failed findings
- `LLM_PROVIDER`: Provider type (defaults to "ollama")
- `CE_MAX_CHAR_BUFFER`: Buffer size for LLM extraction (default: 1500)
- `CE_MAX_WORKERS_EXTRACT`: Parallel workers per extraction (default: 1)
- `CE_CHUNK_TARGET`: Target chunk size in characters (default: 9000)
- `CE_MAX_WORKERS`: Document-level parallelism (default: 1)

### Directory Structure
- `data/`: PDFs for batch processing
- `outputs/`: Generated reports and visualizations
- `rules_packs/`: YAML rule definitions
- `front/`: React frontend application
- `archive/`: Legacy rule evaluation code

### Database Setup Required
The system requires PostgreSQL with the database `contractextract` created. Tables are auto-created on first run via `bootstrap_db.py`.

### Testing Strategy
No formal test suite exists. Testing is performed via:
- Batch processing: `python main.py` against PDFs in `data/`
- API testing: Swagger UI at `http://localhost:8000/docs`
- Frontend testing: Manual testing via React dev server

---

# ContractExtract — MCP + Two-Env Demo Runbook

This file contains **authoritative, copy-ready steps** and **Claude Code prompts** to keep FastAPI+MCP on **Pydantic v2** while LangExtract remains on **Pydantic v1**, and to expose our existing FastAPI features via **MCP** for LibreChat.

---

## Goals

- **Two isolated Python envs**:
  - `.venv-v2` → FastAPI 0.103.x, MCP SDK, **Pydantic v2**.
  - `.venv-v1` → LangExtract pipeline, **Pydantic v1**.
- **MCP wrapper** mounted at `/mcp` inside our existing FastAPI app so **LibreChat** can call tools.
- Everything runnable on **Windows 11**.

---

## Requirements (once)

- Python 3.11
- Windows PowerShell
- (Optional) LibreChat 1.x (may be Dockerized)
- This repo contains: `app.py`, `db.py`, `schemas.py`, `ingest.py`, `evaluator.py`, `rulepack_*`, etc.

---

## 1) Environments (Pydantic split)

### 1.1 Create/refresh `.venv-v2` (FastAPI + MCP; Pydantic v2)
> Run in repo root
```powershell
py -3.11 -m venv .venv-v2
.\.venv-v2\Scripts\Activate.ps1
python -m pip install -U pip wheel
pip install "mcp[cli]" fastapi==0.103.* uvicorn[standard]==0.30.* sqlalchemy psycopg2-binary pyyaml pdfplumber
```
**Notes:**
- `.venv-v2` is used to run `uvicorn app:app` and serve MCP at `/mcp`.
- MCP + FastAPI 0.103.x require Pydantic v2.

### 1.2 Create/refresh `.venv-v1` (LangExtract; Pydantic v1)
```powershell
py -3.11 -m venv .venv-v1
.\.venv-v1\Scripts\Activate.ps1
python -m pip install -U pip wheel
pip install "pydantic<2" pdfplumber
# Add your working LangExtract version here:
# pip install langextract==<your_working_version>
deactivate
```

**Optional** (only if you run a minimal v1 service for bridging):
```powershell
.\.venv-v1\Scripts\Activate.ps1
pip install fastapi==0.95.* uvicorn[standard]==0.22.*
deactivate
```

## 2) MCP integration (mount into FastAPI)

### 2.1 Folder layout
We do **not** move business logic. We add a thin MCP wrapper:
```
contractextract/
├── app.py                  # existing FastAPI app
├── db.py, schemas.py, evaluator.py, ingest.py, rulepack_*.py, ...
└── mcp_server/             # NEW: MCP wrapper only
    ├── __init__.py
    ├── server.py           # creates FastMCP and mounts at /mcp
    └── tools.py            # MCP tools that call our existing code
```

### 2.2 Run (with MCP mount)
```powershell
.\.venv-v2\Scripts\Activate.ps1
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```
- **FastAPI docs**: http://127.0.0.1:8000/docs
- **MCP base** (mounted): http://127.0.0.1:8000/mcp *(not visible in Swagger; that's expected)*

### 2.3 LibreChat config (client → server)
Add to your `librechat.yaml`:
```yaml
mcpServers:
  contractextract:
    type: "streamable-http"
    url: "http://localhost:8000/mcp"
    initTimeout: 150000
    serverInstructions: true
```

If LibreChat runs in Docker on Windows:
```yaml
url: "http://host.docker.internal:8000/mcp"
```

## 3) Optional bridge (keep LangExtract on v1)

If migrating LangExtract to Pydantic v2 is not feasible today, run a tiny v1 FastAPI service on port 8091 that exposes `POST /extract`. The v2 app calls it via HTTP.

**Demo run suggestion:**

**Terminal A** (v1):
```powershell
.\.venv-v1\Scripts\Activate.ps1
uvicorn langextract_service:app --host 127.0.0.1 --port 8091 --reload
```

**Terminal B** (v2):
```powershell
.\.venv-v2\Scripts\Activate.ps1
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

## 4) Validation checklist

- `.venv-v2` active & server running on `:8000`.
- LibreChat `mcpServers.contractextract.url` points to the correct URL.
- In LibreChat:
  - **New chat** → confirm ContractExtract MCP tools are listed.
  - Call `list_rulepacks` (stub initially; wire to DB later).
- **If timeout:**
  - Increase `initTimeout`.
  - Verify port/URL; check server logs.
  - If Dockerized client: use `host.docker.internal`.

## 5) Ready-to-use Claude Code prompts

Paste one prompt at a time into Claude Code. It will propose diffs; click **Apply**.

### 5.1 Scaffold MCP wrapper (files only; no business logic yet)
```markdown
[Claude Code Prompt] Scaffold MCP wrapper mounted at /mcp

Create folder `mcp_server/` with:
1) `__init__.py` (empty)
2) `server.py` that:
   - uses `from mcp.server.fastmcp import FastMCP`
   - creates `mcp = FastMCP("ContractExtract MCP")`
   - registers 3 stub tools with return placeholders:
       - list_rulepacks() -> list of {name, version}
       - get_rulepack(name: str, version: str | None = None)
       - analyze(req: {document_path?, document_text?, doc_type_hint?})
   - imports `from app import app as fastapi_app`
   - mounts MCP at `/mcp` with `fastapi_app.mount("/mcp", mcp.streamable_http_app())`
3) `tools.py` containing the stub tool functions (called by server.py).

Do not edit `app.py` or move business logic. Keep stubs simple so tool discovery works immediately.
Output a short runbook at the end with:
- venv activation command
- `uvicorn app:app --host 127.0.0.1 --port 8000 --reload`
- the LibreChat `mcpServers` YAML snippet.
```

### 5.2 Create helper scripts to switch envs quickly (optional)
```r
[Claude Code Prompt] Create Windows PowerShell helper scripts

Create folder `scripts/` with two files:

- scripts/use-v1.ps1
  ----
  param([switch]$Run)
  . .\.venv-v1\Scripts\Activate.ps1
  if ($Run) { uvicorn langextract_service:app --host 127.0.0.1 --port 8091 --reload }
  ----

- scripts/use-v2.ps1
  ----
  param([switch]$Run)
  . .\.venv-v2\Scripts\Activate.ps1
  if ($Run) { uvicorn app:app --host 127.0.0.1 --port 8000 --reload }
  ----

Do not run anything automatically. Just create files. Print usage examples at the end:
- `.\scripts\use-v1.ps1` (activate)
- `.\scripts\use-v1.ps1 -Run` (activate and start v1)
- `.\scripts\use-v2.ps1` / `.\scripts\use-v2.ps1 -Run`
```

### 5.3 (Optional) Build the LangExtract v1 bridge service
```python
[Claude Code Prompt] Create a minimal v1 LangExtract bridge

Create `langextract_service.py` that runs with Pydantic v1:
- FastAPI app `app`
- POST /extract accepts JSON: { "text": str, "prompt": str, "examples": list }
- Calls existing LangExtract extraction flow and returns JSON.
- On error, return {"error": "..."} with HTTP 500.
No business logic invention; just wrap today's extract call.

Also create `bridge_client.py` (v2 side) with:
  def remote_extract(text: str, prompt: str, examples: list, url: str = "http://127.0.0.1:8091/extract") -> dict:
      """POST to the v1 service and return JSON (raise on non-200)."""

At the end, print a short "integration hint" showing where to replace direct `lx.extract(...)` with `remote_extract(...)`.
```

### 5.4 Wire MCP tools to real FastAPI/DB logic (after stubs are visible)
```typescript
[Claude Code Prompt] Implement MCP tools using existing code

In `mcp_server/tools.py`, replace stubs:

- list_rulepacks():
  Query active packs using existing loader/repo and return [{name, version}] (map from your DB rows).

- get_rulepack(name, version?):
  Fetch record by id/version from DB and return {name, version, yaml_text} (use your existing DTO → string).

- analyze(req):
  Accept either document_path or document_text. If path provided, load bytes; otherwise use text.
  Reuse our existing ingestion + evaluator (`ingest.py` and `evaluator.py`) to produce pass/fail + findings.
  Return {doc_type, pass_fail, violations, output_markdown_path} with the same shapes used in the app.

Keep Pydantic v2 models for tool input/output. Add defensive try/except and return informative MCP errors.
```

### 5.5 End-to-end smoke test checklist
```arduino
[Claude Code Prompt] Generate a smoke test guide

Output a step-by-step Windows guide to verify:
1) Start `.venv-v2`, run `uvicorn app:app --port 8000`.
2) LibreChat config points to `http://localhost:8000/mcp` (or host.docker.internal).
3) Start a chat, confirm tools discovered, run `list_rulepacks`.
4) If using v1 bridge: in another terminal, start `langextract_service.py` on 8091 and run an analyze call that internally hits the bridge.
5) Troubleshooting: timeouts, bad URL, port in use, missing `mcp` install.
```

## 6) Troubleshooting

- **MCP not discovered**: wrong URL, server not running, or init too slow → increase `initTimeout`, check logs.
- **Dockerized LibreChat**: use `http://host.docker.internal:8000/mcp` from inside the container.
- **Port in use**: pick another port and update the commands + LibreChat URL.
- **Pydantic errors**: ensure you're in `.venv-v2` for FastAPI+MCP; `.venv-v1` for LangExtract.

## 7) Quick commands (copy/paste)

**Run FastAPI+MCP**
```powershell
.\.venv-v2\Scripts\Activate.ps1
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

**Run LangExtract v1 bridge (optional)**
```powershell
.\.venv-v1\Scripts\Activate.ps1
uvicorn langextract_service:app --host 127.0.0.1 --port 8091 --reload
```

**LibreChat MCP block**
```yaml
mcpServers:
  contractextract:
    type: "streamable-http"
    url: "http://localhost:8000/mcp"
    initTimeout: 150000
    serverInstructions: true
```

---

**Owner's note**: Keep this file (`claude.md`) as the single source of truth for MCP + env setup. Use the prompts above in Claude Code to generate and evolve files safely.

## MCP Smoke Test (Windows)

1) Start FastAPI+MCP (venv-2):
```powershell
.\.venv-v2\Scripts\Activate.ps1
set USE_V1_BRIDGE=0
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

---

# Latest Updates - Enhanced Pipeline & Advanced Features

## Comprehensive System Overhaul (Current Session)

### 1. LLM Explanations Always Enabled
- **Centralized Configuration**: Created `settings.py` with `LLM_EXPLANATIONS_ENABLED = True` as default
- **Per-Request Override**: Added `llm_override` parameter for debugging across API and CLI
- **CLI Support**: Added `--no-llm` flag to main.py (`python main.py --no-llm`)
- **Unified Processing**: Both API and CLI use identical LLM explanation pipeline
- **Budget Controls**: Token limits and timeout protection to prevent runaway costs

### 2. Precise Page + Line Number Citations
- **Enhanced Citation Schema**: Citations now include `page`, `line_start`, `line_end`, `confidence` fields
- **Citation Mapper**: New `citation_mapper.py` with `PageLineMapper` class for accurate position mapping
- **Enhanced Display**: Citations show as `p. 7, lines 22–27, chars [1234-1456]: "quote" (confidence: 1.0)`
- **Page Break Preservation**: Leverages existing `\f` page separators from PDF extraction
- **Confidence Tracking**: Marks low-confidence citations for OCR-needed documents

### 3. Unified API and CLI Execution Paths
- **Single Service Function**: Both API and CLI call identical `make_report()` function
- **Consistent Rendering**: Removed duplicate markdown functions, unified `render_markdown()`
- **Same Pipeline**: Identical citation enhancement, LLM processing, and output generation
- **Metadata Consistency**: Both paths emit identical metadata structure
- **Command Line Arguments**: CLI now supports `--no-llm` for debugging

### 4. Enhanced Document Type Detection
- **Rules-First Scoring**: Weighted keyword analysis with configurable scoring weights
- **Section Header Detection**: Pattern matching for document structure analysis
- **LLM Fallback**: Optional LLM classification for low-confidence cases (configurable threshold)
- **Detailed Metadata**: Includes top 3 candidates with scores, confidence, and reasoning
- **Transparent Selection**: Full audit trail of document type selection process

### 5. Dual Response Format Support
- **JSON Endpoint** (`/preview-run`): Structured response with rich metadata for automation
- **Markdown Endpoint** (`/preview-run.md`): Pure markdown as `text/markdown` for direct download
- **Consistent Processing**: Both endpoints use identical analysis pipeline
- **SwaggerUI Integration**: JSON visible in Swagger, markdown available for browser preview

### 6. Enhanced API Response Structure
- **SHA1 Document Tracking**: Unique document identification and duplicate detection
- **Rich Metadata**: Enhanced `meta` field with comprehensive processing information
- **Document Type Detection**: Complete candidate analysis and selection reasoning
- **Executive Summaries**: Automatic summaries for failed cases with top 3 failing rules
- **Processing Audit**: Full logging with SHA1, pack selection, and timing information

### 7. Comprehensive OpenAPI Documentation
- **Rich Examples**: Complete YAML rule pack examples for strategic alliance and employment
- **Multiple Input Formats**: Examples for both JSON patch and YAML replacement updates
- **Copy-Ready Templates**: Production-ready examples following schema v1.0 standard
- **Clear Documentation**: Detailed endpoint descriptions with use case guidance

## API Improvements (Previous Session)

### 1. Enhanced API Response Tracking
- **SHA1 Hashing**: Added document SHA1 calculation and logging for unique processing verification
- **Metadata Response**: Enhanced `/preview-run` endpoint with `meta` field containing:
  - `filename`: Original document name
  - `sha1`: Document content hash
  - `selected_pack_id`: Rule pack used for analysis
  - `pass_fail`: Overall compliance result
- **Structured Logging**: Added comprehensive logging with filename, SHA1, pack ID, and results

### 2. Improved LLM Explanation System
- **Executive Summary**: Added comprehensive executive summary for failed compliance reports
  - Highlights top 3 failing rules with clear descriptions
  - Risk assessment explaining potential legal/financial liabilities
  - Recommended remediation actions
- **Enhanced LLM Integration**:
  - Better error handling for provider loading and import issues
  - More robust handling of empty or failed LLM responses
  - Cleaner prompt formatting focused on actionable insights
  - Better filtering to avoid processing status findings

### 3. Report Generation Enhancements
- **Executive Summary Section**: Automatically prepended to failed compliance reports
- **Improved Citation Handling**: Better quote truncation and formatting
- **Status Finding Management**: LLM explanation status findings properly excluded from main report
- **Enhanced Markdown Rendering**: Both API and batch processing use consistent formatting

## YAML Rule Pack Schema Standardization (v1.0)

### Schema Version System
- **Current Version**: `"1.0"` - All rule packs must declare this version
- **Version Tracking**: `schema_version` field added to all rule packs for compatibility
- **Future Evolution**: Version system enables safe schema changes while maintaining backward compatibility

### Standardized Schema Structure

#### Required Fields (Must be present):
```yaml
id: "unique_identifier_v1"                    # Unique rule pack identifier
schema_version: "1.0"                         # Schema compatibility version
doc_type_names:                               # Document types for auto-detection
  - "Primary Document Type"
jurisdiction_allowlist:                       # Allowed governing law jurisdictions
  - "United States"
liability_cap:                                # Liability cap policy
  max_cap_amount: 1000000.0                   # Max absolute cap
  max_cap_multiplier: 1.0                     # Max cap as contract multiplier
contract:                                     # Contract value constraints
  max_contract_value: 5000000.0               # Max total contract value
fraud:                                        # Fraud clause requirements
  require_fraud_clause: true
  require_liability_on_other_party: true
prompt: |                                     # Structured LLM extraction prompt
  Standardized prompt format...
examples:                                     # Training examples
  - text: "Sample text"
    extractions: [...]
```

#### Optional Fields:
```yaml
rules:                                        # Extended domain-specific rules
  - id: custom_rule_id
    type: domain.rule_type
    params: {...}
notes: "Description and metadata"             # Documentation
extensions: {...}                             # Custom fields
extensions_schema: {...}                      # Schema for extensions validation
```

### Schema Benefits
- **Interoperability**: All rule packs work with same import/export system
- **Maintainability**: Easy to update multiple rule packs with schema changes
- **Extensibility**: `rules` and `extensions` sections allow domain-specific customizations
- **Quality Assurance**: Automated validation prevents malformed rule packs

### Validation System
- **Validation Script**: `validate_yaml_rulepacks.py` checks all rule packs
- **Automated Checking**: Required fields, data types, structure constraints
- **Schema Compliance**: Validates against declared schema version
- **Error Reporting**: Detailed validation errors with specific line references

### Updated Rule Packs
All rule packs now conform to v1.0 schema:
- ✅ `strategic_alliance.yml` - Reference implementation
- ✅ `employment.yml` - Employment contract rules
- ✅ `noncompete.yml` - Non-compete agreement rules
- ✅ `ip_agreement.yml` - IP assignment rules
- ✅ `joint_venture.yml` - Joint venture rules
- ✅ `promotion.yml` - Marketing promotion rules
- ✅ `servicing.yml` - Service agreement rules
- ✅ `_TEMPLATE.yml` - Standard schema template

### YAML Importer Updates
- **Schema Version Support**: Handles `schema_version` field
- **Extensions Support**: Processes `extensions` and `extensions_schema` fields
- **Backward Compatibility**: Defaults to v1.0 for legacy rule packs

## Development Workflow Improvements

### New Tools and Scripts
- **`validate_yaml_rulepacks.py`**: Comprehensive YAML validation
- **`fix_yaml_files.py`**: Batch YAML fixing utility (used during migration)
- **`_TEMPLATE.yml`**: Canonical rule pack template

### File Organization
```
rules_packs/
├── _TEMPLATE.yml              # Standard schema template
├── strategic_alliance.yml     # Reference implementation
├── employment.yml             # Fixed and validated
├── noncompete.yml             # Fixed and validated
├── ip_agreement.yml           # Fixed and validated
├── joint_venture.yml          # Fixed and validated
├── promotion.yml              # Fixed and validated
└── servicing.yml              # Fixed and validated
```

### Testing and Validation
- **YAML Validation**: All rule packs pass schema validation
- **API Testing**: Enhanced metadata logging for debugging
- **LLM Integration**: Improved error handling and status reporting

## Key Commands for Development

### Validate All Rule Packs
```powershell
python validate_yaml_rulepacks.py
```

### Test API with Enhanced Logging
```powershell
.\.venv-v2\Scripts\Activate.ps1
uvicorn app:app --reload --port 8000
# Check logs for SHA1 hashes and processing details
```

### Import/Update Rule Packs
```powershell
# Via API (maintains schema validation)
curl -X POST http://localhost:8000/rule-packs/import-yaml \
  -H "Content-Type: application/json" \
  -d '{"yaml_text": "..."}'
```

## Future Schema Evolution

### Planned Enhancements (v1.1+)
- Additional optional fields for enhanced metadata
- Extended rule types for specialized domains
- Enhanced validation constraints
- Improved LLM prompt templates

### Migration Strategy
- Schema version tracking enables safe migrations
- Validation system prevents breaking changes
- Backward compatibility maintained across versions

## Enhanced File Structure (Latest Session)

### New Core Components
```
contractextract/
├── settings.py                    # NEW: Centralized configuration
├── citation_mapper.py             # NEW: Page/line position mapping
├── document_classifier.py         # NEW: Enhanced document type detection
├── validate_yaml_rulepacks.py     # Enhanced YAML validation
├── TEST_PLAN.md                   # NEW: Comprehensive testing guide
├── CHANGELOG.md                   # NEW: Version tracking and changes
└── rules_packs/
    ├── _TEMPLATE.yml              # Enhanced standard template
    └── *.yml                      # All files now schema v1.0 compliant
```

### Enhanced API Endpoints
- **`/preview-run`**: Enhanced JSON response with rich metadata
- **`/preview-run.md`**: NEW markdown-only endpoint for direct download
- **`/rule-packs/import-yaml`**: Enhanced with comprehensive OpenAPI examples
- **`/rule-packs/{id}/{version}`**: Enhanced with schema version support

### Testing and Quality Assurance
```powershell
# Comprehensive validation
python validate_yaml_rulepacks.py

# CLI with debugging
python main.py --no-llm

# API testing with rich examples
# Visit http://localhost:8000/docs for interactive examples
```

### Configuration Management
All settings now centralized in `settings.py`:
- **LLM_EXPLANATIONS_ENABLED**: `True` (always on by default)
- **DOC_TYPE_CONFIDENCE_THRESHOLD**: `0.65` (LLM fallback trigger)
- **LLM_MAX_TOKENS_PER_RUN**: `10000` (budget control)
- **Citation settings**: Context chars, quote length limits

### Quality Metrics
- **✅ 100% YAML Validation**: All 8 rule packs pass validation
- **✅ Unified Processing**: API and CLI use identical pipelines
- **✅ Rich Citations**: Page/line numbers with confidence scoring
- **✅ Enhanced Documentation**: Comprehensive OpenAPI examples
- **✅ Executive Summaries**: Auto-generated for failed compliance

### Key Testing Scenarios
1. **Document Upload**: Test with different file types and sizes
2. **Document Type Detection**: Verify auto-detection with confidence scoring
3. **Citation Accuracy**: Check page/line number mapping
4. **LLM Integration**: Test explanations with budget controls
5. **API Response Formats**: JSON vs Markdown endpoints
6. **Schema Validation**: YAML rule pack compliance

## Production Readiness Checklist

### Environment Setup
- [ ] PostgreSQL database running with `contractextract` database
- [ ] `.venv-v2` environment activated with all dependencies
- [ ] LLM provider configured (Ollama or alternative)
- [ ] All YAML rule packs validated with `validate_yaml_rulepacks.py`

### API Functionality
- [ ] Server starts successfully on port 8000
- [ ] SwaggerUI accessible at `/docs` with examples
- [ ] Document upload works with SHA1 tracking
- [ ] Both `/preview-run` and `/preview-run.md` endpoints functional
- [ ] Document type detection provides detailed metadata

### Quality Assurance
- [ ] LLM explanations generate correctly with budget controls
- [ ] Page/line citations appear with confidence scores
- [ ] Executive summaries generated for failed cases
- [ ] API and CLI produce identical results for same input
- [ ] Comprehensive logging shows processing audit trail

## important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.