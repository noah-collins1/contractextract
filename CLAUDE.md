# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend (Python FastAPI)
```bash
# Install dependencies
pip install -r requirements

# Initialize database tables
python bootstrap_db.py

# Run the API server
uvicorn app:app --reload --port 8000

# Run batch processing on PDFs in data/ folder
python main.py
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