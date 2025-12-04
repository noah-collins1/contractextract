# ContractExtract - Comprehensive Project Documentation

**Last Updated:** November 25, 2025
**Version:** 2.0 (Pure MCP Architecture)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Summary](#architecture-summary)
3. [Directory Structure](#directory-structure)
4. [Core Components](#core-components)
5. [Database Schema](#database-schema)
6. [Document Processing Pipeline](#document-processing-pipeline)
7. [Rule Pack System](#rule-pack-system)
8. [Frontend Application](#frontend-application)
9. [LibreChat Integration](#librechat-integration)
10. [Technology Stack](#technology-stack)
11. [Data Flow](#data-flow)
12. [Known Issues & Testing Tasks](#known-issues--testing-tasks)

---

## Project Overview

**ContractExtract** is an intelligent contract analysis and compliance checking system that leverages LLM-powered extraction, configurable rule packs, and automated compliance verification.

### Key Features

- **Pure MCP (Model Context Protocol) Server** - Direct stdio integration with LibreChat
- **16 MCP Tools** - Comprehensive contract analysis and rule pack management
- **PostgreSQL-backed Rule Storage** - Versioned YAML rule packs with lifecycle management
- **LLM-powered Analysis** - Configurable extraction with Ollama (or other providers)
- **PDF Processing** - Advanced text extraction with OCR support for scanned documents
- **Citation Mapping** - Page and line-level references for compliance violations
- **Multi-document Type Support** - Employment, lease, NDA, joint venture, IP agreements, etc.
- **React Frontend** - Modern UI for document analysis and rule pack management
- **Structured Data Extraction** - Extract 60+ lease fields or custom contract data

### Primary Use Cases

1. **Contract Compliance Checking** - Automated validation against company policies
2. **Lease Agreement Analysis** - Extract and validate critical lease terms
3. **Employment Contract Review** - Ensure jurisdiction, liability, and fraud clauses
4. **Document Classification** - Auto-detect contract types
5. **Batch Document Processing** - Analyze multiple contracts with consistent rules

---

## Architecture Summary

### Evolution History

ContractExtract has undergone several architectural transformations:

- **Phase 1**: Separate FastAPI backend + React frontend
- **Phase 2**: File consolidation (23 files → 8 core files)
- **Phase 3**: Pure MCP migration (HTTP → stdio protocol)
- **Phase 4**: LibreChat integration with dual-mode support (MCP + standalone frontend)

### Current Architecture (Phase 4)

```
┌─────────────────────────────────────────────────────────┐
│                    LibreChat                            │
│  ┌──────────────────────────────────────────────────┐   │
│  │         MCP Client (stdio protocol)              │   │
│  └──────────────────┬───────────────────────────────┘   │
└─────────────────────┼───────────────────────────────────┘
                      │ stdio pipes
┌─────────────────────▼───────────────────────────────────┐
│              ContractExtract MCP Server                 │
│                  (mcp_server.py)                        │
│                                                         │
│  ┌────────────────────────────────────────────────┐    │
│  │           16 MCP Tools                         │    │
│  │                                                │    │
│  │  Rule Pack Management (8 tools):              │    │
│  │  • list_all_rulepacks                         │    │
│  │  • list_active_rulepacks                      │    │
│  │  • get_rulepack_details                       │    │
│  │  • get_rulepack_yaml                          │    │
│  │  • list_rulepack_versions                     │    │
│  │  • create_rulepack_from_yaml                  │    │
│  │  • update_rulepack_yaml                       │    │
│  │  • publish_rulepack                           │    │
│  │                                                │    │
│  │  Document Analysis (2 tools):                 │    │
│  │  • analyze_document (full analysis + export)  │    │
│  │  • preview_document_analysis (quick preview)  │    │
│  │                                                │    │
│  │  Utilities (6 tools):                         │    │
│  │  • generate_rulepack_template                 │    │
│  │  • validate_rulepack_yaml                     │    │
│  │  • get_system_info                            │    │
│  │  • deprecate_rulepack                         │    │
│  │  • delete_rulepack                            │    │
│  │  • export_document_analysis                   │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
│  ┌────────────────────────────────────────────────┐    │
│  │         5 Consolidated Core Modules            │    │
│  │                                                │    │
│  │  • infrastructure.py (267 lines)              │    │
│  │    - Configuration management                 │    │
│  │    - Database setup (SQLAlchemy)              │    │
│  │    - Pydantic schemas (RuleSet, Finding, etc) │    │
│  │    - Telemetry and logging                    │    │
│  │                                                │    │
│  │  • contract_analyzer.py (590 lines)           │    │
│  │    - LLM provider factory (Ollama)            │    │
│  │    - Compliance evaluation engine             │    │
│  │    - Lease extraction pipeline                │    │
│  │    - Report generation (Markdown/TXT)         │    │
│  │                                                │    │
│  │  • document_analysis.py (514 lines)           │    │
│  │    - PDF text extraction (pdfplumber)         │    │
│  │    - OCR support (PyMuPDF + Tesseract)        │    │
│  │    - Document type classification             │    │
│  │    - Citation mapping (page/line numbers)     │    │
│  │                                                │    │
│  │  • rulepack_manager.py (313 lines)            │    │
│  │    - SQLAlchemy models (RulePackRecord)       │    │
│  │    - CRUD operations (create/read/update)     │    │
│  │    - YAML import/export                       │    │
│  │    - Versioning and lifecycle management      │    │
│  │                                                │    │
│  │  • export_utils.py (163 lines)                │    │
│  │    - JSON export                              │    │
│  │    - CSV export                               │    │
│  │    - Excel export                             │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
│  ┌────────────────────────────────────────────────┐    │
│  │         PostgreSQL Database                    │    │
│  │                                                │    │
│  │  Table: rule_packs                             │    │
│  │  • Composite PK: (id, version)                │    │
│  │  • Status: draft → active → deprecated        │    │
│  │  • Versioned YAML storage                     │    │
│  │  • JSON fields: rules, examples, extensions   │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│            Standalone Frontend (Optional)               │
│                                                         │
│  ┌────────────────────────────────────────────────┐    │
│  │         React + TypeScript + Vite              │    │
│  │                                                │    │
│  │  Pages:                                        │    │
│  │  • Dashboard (document upload)                 │    │
│  │  • RulePacks (management UI)                   │    │
│  │  • Reports (analysis results)                  │    │
│  │                                                │    │
│  │  Components:                                   │    │
│  │  • DocumentUploader                            │    │
│  │  • RulePackCard                                │    │
│  │  • ComplianceReport                            │    │
│  │  • MarkdownRenderer                            │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
│          ▲ HTTP API (http_bridge.py - legacy)          │
└──────────┼─────────────────────────────────────────────┘
           │
           └─ Can run alongside MCP server for testing
```

### Key Architectural Decisions

1. **Pure stdio MCP Protocol** - No HTTP overhead, direct process communication
2. **Consolidated Modules** - Reduced from 23 to 5 core files for maintainability
3. **Unified Pydantic v2** - Single dependency tree, no version conflicts
4. **PostgreSQL Storage** - Production-ready database with JSONB support
5. **Async/Await** - Efficient concurrent request handling
6. **Modular LLM Providers** - Factory pattern for swapping AI backends

---

## Directory Structure

```
contractextract/
├── 📄 Core Python Modules (5 files)
│   ├── mcp_server.py              # Pure stdio MCP server (959 lines, 16 tools)
│   ├── infrastructure.py          # Config, DB, schemas, telemetry (267 lines)
│   ├── contract_analyzer.py       # Analysis engine + LLM (590 lines)
│   ├── document_analysis.py       # PDF processing + OCR (514 lines)
│   ├── rulepack_manager.py        # Rule pack data access (313 lines)
│   └── export_utils.py            # Export utilities (163 lines)
│
├── 📁 Frontend Application
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── api/               # HTTP client for backend
│   │   │   ├── components/        # Reusable UI components
│   │   │   ├── pages/             # Route pages (Dashboard, RulePacks, Reports)
│   │   │   ├── utils/             # Helper functions
│   │   │   ├── App.tsx            # Main application component
│   │   │   ├── main.tsx           # Application entry point
│   │   │   └── theme.css          # Global styles
│   │   ├── index.html             # HTML template
│   │   ├── package.json           # Dependencies (React, Vite, etc.)
│   │   ├── vite.config.ts         # Vite configuration
│   │   └── tsconfig.json          # TypeScript configuration
│
├── 📁 Rule Pack Definitions (YAML)
│   ├── rules_packs/
│   │   ├── employment.yml         # Employment contract rules
│   │   ├── strategic_alliance.yml # Alliance agreement rules
│   │   ├── noncompete.yml         # Non-compete rules
│   │   ├── ip_agreement.yml       # IP agreement rules
│   │   ├── joint_venture.yml      # Joint venture rules
│   │   ├── promotion.yml          # Promotion agreement rules
│   │   ├── servicing.yml          # Servicing contract rules
│   │   └── _TEMPLATE.yml          # Rule pack template
│
├── 📁 Test Data
│   ├── data/                      # Test PDF documents
│   │   └── test_employment.txt    # Test data
│   ├── stash/                     # Sample contracts
│   │   ├── employment/            # Employment contract samples
│   │   └── lease/                 # Lease agreement samples
│
├── 📁 Output Files
│   └── outputs/                   # Generated analysis reports (MD, TXT, JSON)
│
├── 📁 Configuration & Documentation
│   ├── requirements.txt           # Python dependencies
│   ├── CLAUDE.md                  # Claude Code instructions
│   ├── ARCHITECTURE_ANALYSIS.md   # Legacy architecture analysis
│   ├── PROJECT_OVERVIEW.md        # This document
│   ├── TEST_PLAN.md               # Testing documentation
│   └── EXPOSE_POSTGRES_PORT.md    # Database access guide
│
├── 📁 Utilities & Testing
│   ├── seed_database.py           # Database seeding script
│   ├── test_analyze_local.py      # Local analysis testing
│   ├── test_database.py           # Database connection testing
│   └── test.py                    # General tests
│
├── 📁 Legacy/Archive
│   ├── archive/                   # Old code (FastAPI backend, scripts)
│   └── http_bridge.py             # Legacy HTTP API (for standalone frontend)
│
└── 📁 LibreChat Integration
    └── librechat/                 # LibreChat Docker setup (optional)
```

---

## Core Components

### 1. MCP Server (`mcp_server.py`)

**Purpose:** Pure stdio MCP server providing 16 tools for LibreChat integration.

**Key Functions:**
- `list_all_rulepacks()` - List all rule packs (any status/version)
- `list_active_rulepacks()` - List only active rule packs
- `get_rulepack_details(pack_id, version)` - Get detailed rule pack info
- `get_rulepack_yaml(pack_id, version)` - Retrieve raw YAML
- `list_rulepack_versions(pack_id)` - List all versions of a pack
- `create_rulepack_from_yaml(yaml_content)` - Import new rule pack
- `update_rulepack_yaml(pack_id, version, yaml_content)` - Update draft
- `publish_rulepack(pack_id, version)` - Activate draft rule pack
- `analyze_document(file_path, pack_id, llm_enabled)` - Full analysis with export
- `preview_document_analysis(file_path, pack_id)` - Quick preview
- `generate_rulepack_template()` - Generate YAML template
- `validate_rulepack_yaml(yaml_content)` - Validate before import
- `get_system_info()` - System diagnostics
- `deprecate_rulepack(pack_id, version)` - Mark as deprecated
- `delete_rulepack(pack_id, version)` - Delete (with safety checks)
- `export_document_analysis(file_path, pack_id, format)` - Export to JSON/CSV/Excel

**Architecture:**
- Async/await for concurrent requests
- Direct stdio communication (no HTTP)
- JSON-RPC protocol via MCP SDK
- Automatic database initialization
- Comprehensive error handling

---

### 2. Infrastructure (`infrastructure.py`)

**Purpose:** Centralized configuration, database, schemas, and telemetry.

**Key Components:**

#### Configuration (`ContractExtractSettings`)
```python
DATABASE_URL: str                      # PostgreSQL connection
LLM_EXPLANATIONS_ENABLED: bool         # Default: True
LLM_PROVIDER: str                       # Default: "ollama"
LLM_MAX_TOKENS_PER_RUN: int            # Token budget
LLM_TIMEOUT_SECONDS: int               # LLM timeout
DOC_TYPE_CONFIDENCE_THRESHOLD: float   # Classification threshold
CITATION_CONTEXT_CHARS: int            # Citation context size
```

#### Database Setup
```python
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
```

#### Pydantic Schemas
- `RuleSet` - Compliance rules (jurisdiction, liability, fraud, contract value)
- `Citation` - Page/line citation with confidence score
- `Finding` - Compliance check result (passed/failed, details, citations)
- `LeaseExtraction` - Structured lease data (60+ fields)
- `DocumentReport` - Final analysis report (findings + extraction)
- `ExampleItem` - LLM extraction examples
- `RulePack` - Runtime rule pack representation

#### Telemetry (`go_quiet()`)
- Silences 3rd-party library logging spam
- Configurable via `CE_LOG_LEVEL` environment variable
- Keeps application logs visible

---

### 3. Contract Analyzer (`contract_analyzer.py`)

**Purpose:** Analysis engine with LLM provider support and evaluation logic.

**Key Components:**

#### LLM Provider System
```python
class LLMProvider(ABC):
    @abstractmethod
    def extract(...) -> Any:
        """Extract information using LLM."""

class OllamaProvider(LLMProvider):
    def extract(text, prompt, examples):
        """Extract using Ollama via langextract."""
```

**Supported Providers:**
- Ollama (default) - Local LLM via langextract
- Extensible for OpenAI, Anthropic, etc.

#### Compliance Evaluation
```python
def evaluate_text_against_rules(text: str, rules: RuleSet) -> List[Finding]:
    """
    Evaluate document against 4 hardcoded compliance checks:
    1. Liability cap (within bounds)
    2. Contract value (within limit)
    3. Fraud clause (present and assigned to other party)
    4. Jurisdiction (in allowlist)
    """
```

**Current Limitation:** Only 4 hardcoded checks are evaluated. Custom rules from YAML `rules:` section are **stored but not executed**.

#### Lease Extraction Pipeline
```python
def extract_lease_fields(text, llm_prompt, examples) -> LeaseExtraction:
    """
    Extract structured lease data using LLM.
    Returns 60+ lease fields (property, tenant, dates, rent, etc.)
    """
```

#### Report Generation
```python
def make_report(document_name, text, rules, pack_data) -> DocumentReport:
    """
    Generate compliance report with findings and optional extraction.
    """

def render_markdown(report: DocumentReport) -> str:
    """
    Render Markdown report with:
    - Executive summary
    - Compliance findings (PASS/FAIL)
    - Citations with page/line numbers
    - Optional lease abstract
    """
```

---

### 4. Document Analysis (`document_analysis.py`)

**Purpose:** PDF processing, OCR, document classification, and citation mapping.

**Key Functions:**

#### PDF Text Extraction
```python
def extract_text_with_pages(pdf_path: str) -> str:
    """
    Extract text with automatic OCR detection.
    Uses pdfplumber for text PDFs, PyMuPDF + Tesseract for scanned PDFs.
    Returns text with \f (form-feed) as page separators.
    """

def ingest_bytes_to_text(data: bytes, filename: str) -> str:
    """
    Accept raw PDF bytes, extract text with OCR support.
    Used by MCP server for file upload processing.
    """
```

**OCR Support:**
- Automatic scanned PDF detection (`is_scanned_pdf()`)
- PyMuPDF + Tesseract integration
- Configurable Tesseract path (auto-detects on Windows)
- Fallback to text extraction if OCR unavailable

#### Document Type Classification
```python
def guess_doc_type_id(text: str, available_packs: List[RulePack]) -> Tuple[str, float]:
    """
    Classify document type using:
    1. Rules-based keyword matching (fast)
    2. LLM fallback if confidence < threshold

    Returns: (pack_id, confidence_score)
    """
```

**Classification Strategy:**
- Keyword-based scoring for each doc type
- Confidence threshold (default 0.65)
- Optional LLM fallback for ambiguous documents

#### Citation Mapping
```python
def map_citation_to_pages(
    text_with_page_breaks: str,
    char_start: int,
    char_end: int
) -> Tuple[int, int, int]:
    """
    Map character positions to (page, line_start, line_end).
    Supports page-aware citation generation.
    """
```

---

### 5. Rule Pack Manager (`rulepack_manager.py`)

**Purpose:** Database models, CRUD operations, and YAML import/export.

**Database Model:**
```python
class RulePackRecord(Base):
    __tablename__ = "rule_packs"

    # Composite Primary Key
    id: str                        # e.g., "employment_v1"
    version: int                   # e.g., 1, 2, 3

    # Metadata
    status: str                    # draft | active | deprecated
    schema_version: str            # YAML schema version (1.0)

    # Content
    doc_type_names: List[str]      # ["Employment Agreement", "Offer Letter"]
    ruleset_json: dict             # RuleSet as JSON
    rules_json: List[dict]         # Custom rules (future use)
    llm_prompt: str                # Extraction prompt
    llm_examples_json: List[dict]  # LLM examples

    # Extensions
    extensions_json: dict          # Custom metadata
    extensions_schema_json: dict   # Extension schema

    # Provenance
    raw_yaml: str                  # Original YAML
    notes: str                     # Documentation
    created_by: str                # Author
    created_at: datetime
    updated_at: datetime
```

**CRUD Operations:**
```python
# Create
def import_rulepack_yaml(yaml_content: str, created_by: str = None) -> RulePackRecord

# Read
def list_active_rulepacks() -> List[dict]
def get_latest_version(pack_id: str) -> RulePackRecord
def load_packs_for_runtime() -> List[RuntimeRulePack]

# Update
def update_draft_yaml(pack_id: str, version: int, yaml_content: str) -> RulePackRecord

# Publish
def publish_pack(pack_id: str, version: int) -> RulePackRecord

# Delete
def delete_pack(pack_id: str, version: int)
```

**Lifecycle Management:**
```
1. Create     → draft status (import_rulepack_yaml)
2. Edit       → update draft only (update_draft_yaml)
3. Validate   → check schema compliance
4. Publish    → active status (publish_pack)
5. Deprecate  → deprecated status (no longer used)
6. Delete     → permanent removal (with safety checks)
```

---

### 6. Export Utilities (`export_utils.py`)

**Purpose:** Export analysis results to multiple formats.

**Supported Formats:**
- **JSON** - Full structured data export
- **CSV** - Flattened findings for spreadsheet analysis
- **Excel** - Multi-sheet workbook with metadata

**Functions:**
```python
def export_to_json(report: DocumentReport, output_path: str)
def export_to_csv(report: DocumentReport, output_path: str)
def export_to_excel(report: DocumentReport, output_path: str)
```

---

## Database Schema

### PostgreSQL Database: `contractextract`

#### Table: `rule_packs`

**Primary Key:** Composite `(id, version)`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | VARCHAR(128) | NO | Rule pack identifier |
| `version` | INTEGER | NO | Version number (1, 2, 3...) |
| `status` | ENUM | NO | draft / active / deprecated |
| `schema_version` | VARCHAR(16) | NO | YAML schema version (1.0) |
| `doc_type_names` | JSONB | NO | List of document type names |
| `ruleset_json` | JSONB | NO | RuleSet configuration |
| `rules_json` | JSONB | NO | Custom rule types (future) |
| `llm_prompt` | TEXT | YES | LLM extraction prompt |
| `llm_examples_json` | JSONB | NO | LLM extraction examples |
| `extensions_json` | JSONB | YES | Custom metadata |
| `extensions_schema_json` | JSONB | YES | Extension schema |
| `raw_yaml` | TEXT | YES | Original YAML content |
| `notes` | TEXT | YES | Documentation |
| `created_by` | VARCHAR(128) | YES | Author identifier |
| `created_at` | TIMESTAMP | NO | Creation timestamp |
| `updated_at` | TIMESTAMP | NO | Last update timestamp |

**Indexes:**
- Primary key on `(id, version)`
- Recommended: Index on `status` for active pack queries
- Recommended: Index on `created_at` for version history

**Sample Query:**
```sql
-- Get all active rule packs
SELECT id, version, doc_type_names, created_at
FROM rule_packs
WHERE status = 'active'
ORDER BY id, version DESC;

-- Get latest version of a specific pack
SELECT *
FROM rule_packs
WHERE id = 'employment_v1'
ORDER BY version DESC
LIMIT 1;

-- List all versions of a pack
SELECT version, status, created_at, updated_at
FROM rule_packs
WHERE id = 'employment_v1'
ORDER BY version DESC;
```

---

## Document Processing Pipeline

### End-to-End Flow

```
┌──────────────────────────────────────────────────────────┐
│ 1. Document Upload                                       │
│    • PDF bytes received via MCP tool or HTTP upload     │
│    • File saved to temporary location                   │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ 2. Text Extraction (document_analysis.py)               │
│    • pdfplumber for text-based PDFs                     │
│    • PyMuPDF + Tesseract OCR for scanned PDFs           │
│    • Page breaks preserved as \f characters             │
│    • Output: Full text with page markers                │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ 3. Document Type Classification                         │
│    • Rules-based keyword scoring                        │
│    • Compare against available rule pack doc_type_names │
│    • If confidence < 0.65 → LLM fallback classification │
│    • Output: (pack_id, confidence_score)                │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ 4. Load Rule Pack                                        │
│    • Query database for active pack matching pack_id    │
│    • Load ruleset_json → RuleSet object                 │
│    • Load llm_prompt and llm_examples_json              │
│    • Output: RulePack with rules and extraction config  │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ 5. Compliance Evaluation (contract_analyzer.py)         │
│    • Check 1: Liability cap (within bounds?)            │
│    • Check 2: Contract value (within limit?)            │
│    • Check 3: Fraud clause (present and assigned?)      │
│    • Check 4: Jurisdiction (in allowlist?)              │
│    • Generate Finding objects with citations            │
│    • Output: List[Finding] (4 compliance findings)      │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ 6. LLM Explanations (optional)                          │
│    • For each failed finding, call LLM                  │
│    • Generate natural language explanation              │
│    • Add llm_explanation field to Finding               │
│    • Respect token budget (LLM_MAX_TOKENS_PER_RUN)      │
│    • Output: Enhanced findings with explanations        │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ 7. Lease Extraction (if llm_prompt present)             │
│    • Call LLM with extraction prompt + examples         │
│    • Parse structured output (60+ fields)               │
│    • Validate and normalize field values                │
│    • Output: LeaseExtraction object                     │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ 8. Report Generation                                     │
│    • Create DocumentReport object                       │
│    •   - document_name                                  │
│    •   - passed_all (bool)                              │
│    •   - findings (List[Finding])                       │
│    •   - extraction (LeaseExtraction, optional)         │
│    • Render to Markdown format                          │
│    • Save to outputs/ directory                         │
│    • Output: Markdown report + DocumentReport object    │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ 9. Export (optional)                                     │
│    • Export to JSON (full structured data)              │
│    • Export to CSV (flattened findings)                 │
│    • Export to Excel (multi-sheet workbook)             │
│    • Output: Exported files in requested format         │
└──────────────────────────────────────────────────────────┘
```

### Example: Employment Contract Analysis

**Input:** `employment_contract.pdf`

**Step 1: Text Extraction**
```
Extracted text (3 pages):
"EMPLOYMENT AGREEMENT\n\nThis Employment Agreement..."
[Page break: \f]
"Article 2: Compensation and Benefits..."
[Page break: \f]
"Article 5: Governing Law - Delaware..."
```

**Step 2: Classification**
```python
guess_doc_type_id(text, available_packs)
# Returns: ("employment_v1", 0.87)
```

**Step 3: Load Rules**
```yaml
id: employment_v1
doc_type_names:
  - Employment Agreement
  - Offer Letter
jurisdiction_allowlist:
  - United States
liability_cap:
  max_cap_amount: 1000000.0
contract:
  max_contract_value: 5000000.0
fraud:
  require_fraud_clause: true
```

**Step 4: Evaluate**
```python
findings = [
    Finding(
        rule_id="jurisdiction_present_and_allowed",
        passed=True,
        details="Jurisdiction 'Delaware' found and is allowed.",
        citations=[Citation(char_start=1523, char_end=1531, quote="Delaware", page=3)]
    ),
    Finding(
        rule_id="fraud_clause_present_and_assigned",
        passed=False,
        details="Fraud clause not found or not assigned to other party.",
        citations=[]
    ),
    # ...
]
```

**Step 5: Generate Report**
```markdown
# Compliance Report — employment_contract.pdf

**Status:** ❌ FAILED (2 of 4 checks passed)

## Executive Summary
This document FAILED compliance review. The following critical issues were identified:
- Fraud clause not found or not assigned to other party
- Liability cap exceeds maximum allowed

## Fraud Clause Present And Assigned
- **Result:** FAIL
- **Details:** Fraud clause not found or not assigned to other party.

## Jurisdiction Present And Allowed
- **Result:** PASS
- **Details:** Jurisdiction 'Delaware' found and is allowed.
- **Citations:**
  - Page 3: "...Governing Law - Delaware..."
```

---

## Rule Pack System

### YAML Schema v1.0

```yaml
# Rule Pack Identifier
id: "employment_v1"

# Schema version (always "1.0")
schema_version: "1.0"

# Document type names (for classification)
doc_type_names:
  - "Employment Agreement"
  - "Offer Letter"
  - "Employment Contract"

# Compliance Rules
jurisdiction_allowlist:
  - "United States"
  - "Canada"
  - "European Union"

liability_cap:
  max_cap_amount: 1000000.0      # $1M max
  max_cap_multiplier: 1.0         # or 1x contract value

contract:
  max_contract_value: 5000000.0   # $5M max total value

fraud:
  require_fraud_clause: true
  require_liability_on_other_party: true

# LLM Extraction (optional)
prompt: |
  Extract the following information from this employment agreement:
  - Employee name
  - Start date
  - Salary
  - Benefits
  - Termination notice period

examples:
  - text: "John Doe will commence employment on January 1, 2024 at a salary of $120,000/year."
    extractions:
      - label: "employee_name"
        span: "John Doe"
        attributes: {}
      - label: "start_date"
        span: "January 1, 2024"
        attributes: {}
      - label: "salary"
        span: "$120,000/year"
        attributes:
          amount: 120000
          frequency: "yearly"

# Documentation
notes: |
  Employment contract compliance rules for US-based hires.
  Updated: 2024-10-01
```

### Available Rule Packs

Located in `rules_packs/`:

1. **employment.yml** - Employment agreements, offer letters
2. **strategic_alliance.yml** - Strategic partnership agreements
3. **noncompete.yml** - Non-compete and non-solicitation agreements
4. **ip_agreement.yml** - Intellectual property agreements
5. **joint_venture.yml** - Joint venture contracts
6. **promotion.yml** - Promotional partnership agreements
7. **servicing.yml** - Service-level agreements
8. **_TEMPLATE.yml** - Template for creating new rule packs

### Rule Pack Lifecycle

```
┌─────────────────────────────────────────────────┐
│ 1. CREATE (draft)                               │
│    • Import YAML via create_rulepack_from_yaml  │
│    • Assigned version 1                         │
│    • Status: draft                              │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 2. EDIT (draft only)                            │
│    • Update YAML via update_rulepack_yaml       │
│    • Can only edit draft status packs           │
│    • Increments updated_at timestamp            │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 3. VALIDATE                                     │
│    • Check schema compliance                    │
│    • Validate doc_type_names not empty          │
│    • Ensure ruleset_json is valid               │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 4. PUBLISH (draft → active)                     │
│    • Change status to active                    │
│    • Previous active version → deprecated       │
│    • Now available for document analysis        │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 5. DEPRECATE (active → deprecated)              │
│    • Manually deprecate old versions            │
│    • No longer used for new analysis            │
│    • Retained for historical reference          │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 6. DELETE (optional)                            │
│    • Permanently remove from database           │
│    • Safety check: prevent deleting active      │
│    • Cannot be undone                           │
└─────────────────────────────────────────────────┘
```

---

## Frontend Application

### Technology Stack

- **React 18.3** - UI framework
- **TypeScript 5.5** - Type safety
- **Vite 5.4** - Build tool and dev server
- **React Router 6.26** - Client-side routing
- **React Hook Form 7.53** - Form management
- **React Query 5.51** - Server state management
- **Axios 1.7** - HTTP client
- **React Markdown 9.0** - Markdown rendering

### Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts              # Axios HTTP client configuration
│   │
│   ├── components/
│   │   ├── DocumentUploader.tsx   # File upload component
│   │   ├── RulePackCard.tsx       # Rule pack display card
│   │   ├── ComplianceReport.tsx   # Analysis result viewer
│   │   ├── MarkdownRenderer.tsx   # Markdown report display
│   │   └── Header.tsx             # App header/navigation
│   │
│   ├── pages/
│   │   ├── Dashboard.tsx          # Document upload and analysis
│   │   ├── RulePacks.tsx          # Rule pack management
│   │   ├── Reports.tsx            # Analysis results history
│   │   └── NotFound.tsx           # 404 page
│   │
│   ├── utils/
│   │   ├── formatters.ts          # Date, number formatting
│   │   └── validators.ts          # Input validation
│   │
│   ├── App.tsx                    # Main app with routing
│   ├── main.tsx                   # Entry point
│   └── theme.css                  # Global styles
│
├── index.html                     # HTML template
├── package.json                   # Dependencies
├── vite.config.ts                 # Vite configuration
└── tsconfig.json                  # TypeScript config
```

### Key Features

**1. Document Upload & Analysis**
- Drag-and-drop PDF upload
- Rule pack selection
- LLM toggle (enable/disable explanations)
- Real-time analysis progress
- Markdown report preview

**2. Rule Pack Management**
- List all rule packs with status badges
- Create new rule packs from YAML
- Edit draft rule packs
- Publish drafts to active
- Deprecate/delete rule packs
- Version history viewer

**3. Analysis Reports**
- Markdown rendering with syntax highlighting
- Citation navigation (jump to page/line)
- Export to JSON/CSV/Excel
- Report history with search/filter
- Side-by-side comparison

### Running the Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (http://localhost:5173)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### API Integration

Frontend communicates with `http_bridge.py` (legacy HTTP API):

```typescript
// src/api/client.ts
import axios from 'axios';

const client = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
});

// Example: Upload and analyze document
export const analyzeDocument = async (
  file: File,
  packId: string,
  llmEnabled: boolean
) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('pack_id', packId);
  formData.append('llm_enabled', String(llmEnabled));

  const response = await client.post('/api/analyze', formData);
  return response.data;
};
```

**Note:** The HTTP bridge is a legacy component. Production deployments should use LibreChat with the MCP server for optimal integration.

---

## LibreChat Integration

### Configuration

Add to `librechat.yaml`:

```yaml
mcpServers:
  contractextract:
    command: "python"
    args: ["mcp_server.py"]
    cwd: "C:\\Users\\noahc\\PycharmProjects\\langextract"
    initTimeout: 150000
    serverInstructions: true
    env:
      DATABASE_URL: "postgresql+psycopg2://postgres:password@localhost:5432/contractextract"
      LLM_PROVIDER: "ollama"
      CE_LOG_LEVEL: "INFO"
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg2://postgres:1219@localhost:5432/contractextract` | PostgreSQL connection string |
| `LLM_PROVIDER` | `ollama` | LLM provider (ollama, openai, etc.) |
| `LLM_MAX_TOKENS_PER_RUN` | `10000` | Token budget per analysis |
| `LLM_TIMEOUT_SECONDS` | `30` | LLM request timeout |
| `CE_LOG_LEVEL` | `ERROR` | Logging level (DEBUG, INFO, ERROR) |
| `DOC_TYPE_CONFIDENCE_THRESHOLD` | `0.65` | Classification confidence threshold |
| `DOC_TYPE_USE_LLM_FALLBACK` | `true` | Use LLM for ambiguous classifications |

### Using ContractExtract in LibreChat

**1. List Available Rule Packs**
```
User: "List all active rule packs"
Assistant: [Calls list_active_rulepacks MCP tool]
```

**2. Analyze a Document**
```
User: "Analyze this employment contract"
[Uploads employment_contract.pdf]
Assistant: [Calls analyze_document with auto-detected pack_id]
```

**3. Create a New Rule Pack**
```
User: "Create a rule pack for NDA agreements"
Assistant: [Calls generate_rulepack_template]
Assistant: "Here's a template. Please provide your rules."
User: [Provides YAML]
Assistant: [Calls create_rulepack_from_yaml]
```

**4. Get System Information**
```
User: "Check ContractExtract system status"
Assistant: [Calls get_system_info]
```

### PostgreSQL Access

To access the PostgreSQL database from your local machine (for debugging, seeding, etc.):

**Option 1: Expose Port (Development Only)**

Create `docker-compose.override.yml` in LibreChat directory:

```yaml
version: '3.4'

services:
  contractextract-db:
    ports:
      - "5433:5432"  # Expose on port 5433
```

Restart LibreChat:
```bash
docker-compose down
docker-compose up -d
```

Connect from local machine:
```bash
# PowerShell
$env:DATABASE_URL="postgresql+psycopg2://postgres:contractextract_pass@localhost:5433/contractextract"
python seed_database.py
```

**Option 2: Docker Exec (Production)**

Execute commands directly in the container:
```bash
docker exec -it librechat-contractextract-db-1 psql -U postgres -d contractextract
```

---

## Technology Stack

### Backend (Python 3.11+)

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Core** | Python | 3.11+ | Runtime |
| **MCP SDK** | mcp[cli] | 1.14.1 | Model Context Protocol |
| **Data Validation** | Pydantic | 2.11.9 | Schema validation |
| **Database** | SQLAlchemy | 2.0.36 | ORM |
| | psycopg2-binary | 2.9.20 | PostgreSQL driver |
| **LLM** | langextract | 1.0.9 | Information extraction |
| | google-genai | 1.30.0 | Google Gemini (optional) |
| **PDF Processing** | pdfplumber | 0.11.6 | Text extraction |
| | PyMuPDF | 1.24.14 | OCR support |
| | pytesseract | 0.3.13 | OCR engine |
| | Pillow | 11.3.0 | Image processing |
| **HTTP** | httpx | 0.28.1 | Async HTTP client |
| | aiohttp | 3.12.15 | Async HTTP |
| | requests | 2.32.4 | Sync HTTP |
| **Data** | pandas | 2.3.1 | Data manipulation |
| | numpy | 2.3.2 | Numerical operations |
| **Utilities** | PyYAML | 6.0.2 | YAML parsing |
| | python-dotenv | 1.1.1 | Environment variables |
| | rich | 14.1.0 | Terminal UI |

### Frontend (React)

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Framework** | React | 18.3 | UI framework |
| | TypeScript | 5.5 | Type safety |
| **Build** | Vite | 5.4 | Build tool |
| **Routing** | React Router | 6.26 | Client routing |
| **Forms** | React Hook Form | 7.53 | Form management |
| | Zod | 3.23 | Schema validation |
| **State** | React Query | 5.51 | Server state |
| **HTTP** | Axios | 1.7 | API client |
| **Rendering** | React Markdown | 9.0 | Markdown display |
| | remark-gfm | 4.0 | GitHub Flavored Markdown |

### Database

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **DBMS** | PostgreSQL | 12+ | Relational database |
| **Schema** | SQLAlchemy ORM | Table definitions |
| **Migrations** | Manual | Schema evolution |
| **JSON Storage** | JSONB | Flexible rule/metadata storage |

### Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **MCP Protocol** | stdio | LibreChat communication |
| **Web Server** | Uvicorn (legacy) | HTTP API (optional) |
| **Container** | Docker (optional) | Deployment |
| **Process Manager** | LibreChat MCP Manager | MCP server lifecycle |

---

## Data Flow

### MCP Tool Invocation Flow

```
┌────────────────────────────────────────────────────────┐
│ LibreChat User Interface                               │
│                                                        │
│ User: "Analyze this employment contract"              │
│ [Uploads: employment_contract.pdf]                    │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼ stdio (JSON-RPC)
┌────────────────────────────────────────────────────────┐
│ MCP Client (in LibreChat process)                     │
│                                                        │
│ 1. Detect tool: analyze_document                      │
│ 2. Prepare parameters:                                │
│    {                                                   │
│      "file_path": "/tmp/employment_contract.pdf",     │
│      "pack_id": null,  // auto-detect                 │
│      "llm_enabled": true                              │
│    }                                                   │
│ 3. Send JSON-RPC request via stdio                    │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼ stdio pipe
┌────────────────────────────────────────────────────────┐
│ mcp_server.py (ContractExtract MCP Server)            │
│                                                        │
│ @server.call_tool()                                    │
│ async def handle_call_tool(name, arguments):          │
│     if name == "analyze_document":                    │
│         return await tool_analyze_document(arguments) │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ tool_analyze_document()                                │
│                                                        │
│ 1. Extract text from PDF                              │
│    text = ingest_bytes_to_text(file_bytes)            │
│                                                        │
│ 2. Load all active rule packs                         │
│    packs = load_packs_for_runtime()                   │
│                                                        │
│ 3. Classify document type                             │
│    pack_id, confidence = guess_doc_type_id(text)      │
│                                                        │
│ 4. Generate compliance report                         │
│    report = make_report(text, pack_data)              │
│                                                        │
│ 5. Save Markdown report                               │
│    md_path = save_markdown(report)                    │
│                                                        │
│ 6. Return result to MCP client                        │
│    return {                                            │
│      "status": "success",                             │
│      "markdown_report": md_content,                   │
│      "output_path": md_path,                          │
│      "passed_all": report.passed_all                  │
│    }                                                   │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼ JSON response via stdio
┌────────────────────────────────────────────────────────┐
│ MCP Client (in LibreChat)                             │
│                                                        │
│ 1. Receive JSON response                              │
│ 2. Parse markdown_report field                        │
│ 3. Display to user in chat                            │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ LibreChat UI                                           │
│                                                        │
│ Assistant: "Analysis complete! ✅"                     │
│                                                        │
│ # Compliance Report — employment_contract.pdf         │
│                                                        │
│ **Status:** ✅ PASSED (4 of 4 checks passed)          │
│                                                        │
│ ## Liability Cap Present And Within Bounds            │
│ - **Result:** PASS                                     │
│ ...                                                    │
└────────────────────────────────────────────────────────┘
```

### Database Query Flow

```
┌────────────────────────────────────────────────────────┐
│ MCP Tool: list_active_rulepacks                        │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ rulepack_manager.py: list_active_rulepacks()           │
│                                                        │
│ with SessionLocal() as db:                            │
│     stmt = (                                           │
│         select(RulePackRecord)                         │
│         .where(RulePackRecord.status == "active")      │
│         .order_by(RulePackRecord.id, desc(version))    │
│     )                                                   │
│     results = db.execute(stmt).scalars().all()         │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼ SQL Query
┌────────────────────────────────────────────────────────┐
│ PostgreSQL Database                                    │
│                                                        │
│ SELECT * FROM rule_packs                              │
│ WHERE status = 'active'                               │
│ ORDER BY id, version DESC;                            │
│                                                        │
│ Result:                                                │
│ ┌─────────────────┬─────────┬────────┬──────────────┐ │
│ │ id              │ version │ status │ doc_types    │ │
│ ├─────────────────┼─────────┼────────┼──────────────┤ │
│ │ employment_v1   │ 2       │ active │ ["Employ..."]│ │
│ │ lease_v1        │ 1       │ active │ ["Lease..."] │ │
│ │ nda_v1          │ 3       │ active │ ["NDA..."]   │ │
│ └─────────────────┴─────────┴────────┴──────────────┘ │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼ Convert to Pydantic
┌────────────────────────────────────────────────────────┐
│ rulepack_manager.py                                    │
│                                                        │
│ packs = []                                             │
│ for record in results:                                │
│     pack = {                                           │
│         "id": record.id,                               │
│         "version": record.version,                     │
│         "status": record.status,                       │
│         "doc_type_names": record.doc_type_names,       │
│         "created_at": record.created_at.isoformat()    │
│     }                                                   │
│     packs.append(pack)                                 │
│                                                        │
│ return packs                                           │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼ Return to MCP tool
┌────────────────────────────────────────────────────────┐
│ MCP Server: Return JSON response                      │
│                                                        │
│ {                                                      │
│   "rule_packs": [                                      │
│     {                                                  │
│       "id": "employment_v1",                           │
│       "version": 2,                                    │
│       "status": "active",                              │
│       "doc_type_names": ["Employment Agreement"],      │
│       "created_at": "2024-10-01T12:00:00Z"             │
│     },                                                  │
│     ...                                                 │
│   ]                                                     │
│ }                                                       │
└────────────────────────────────────────────────────────┘
```

---

## Known Issues & Testing Tasks

### Critical Issue: PDF File Upload Investigation

**Discovered:** 2025-10-03
**Status:** 🔴 Needs Investigation

#### Problem Description

When uploading a real PDF to LibreChat and requesting analysis via the ContractExtract MCP tools, the system appears to:
1. **Hallucinate example data** instead of processing the actual PDF
2. **Use template/example responses** from prompts instead of real analysis
3. **File upload mechanism failing** between LibreChat and MCP tools

#### Evidence

- User uploaded actual PDF, but response contained generic example data
- Fixed timestamps and placeholder file paths suggest template responses
- Unclear if MCP stdio protocol properly handles file uploads

#### Possible Root Causes

1. **LibreChat File Handling Conflicts**
   - Multiple MCP servers (ContractExtract + RAGsearch) may conflict
   - MCP protocol may not support file uploads via stdio
   - LibreChat may not pass file references to MCP tools correctly

2. **MCP Tool Parameter Handling**
   - `analyze_document` expects file path parameter
   - LibreChat may not convert file uploads to accessible paths
   - File might be uploaded but path not passed to MCP server

3. **CLI Prompt Too Complex**
   - Examples in prompts may cause LLM to hallucinate instead of using tools
   - Need to simplify and clearly mark examples as templates

4. **Agent vs Direct Tool Call Confusion**
   - Agent wrapper may prefer text generation over tool calls
   - Need to test direct MCP tool invocation

#### Testing Tasks (Priority Order)

**🔴 HIGH PRIORITY**

1. Test direct MCP tool call (no CLI agent wrapper)
2. Verify MCP stdio protocol file handling capabilities
3. Investigate RAGsearch conflict (disable temporarily and test)

**🟡 MEDIUM PRIORITY**

4. Simplify CLI prompt (remove/reduce examples)
5. Test each MCP tool individually
6. Verify markdown report integration

**🟢 LOW PRIORITY**

7. Optimize agent instructions
8. Compare different LLM model behaviors

#### Success Criteria

File upload working when:
- ✅ Actual filename appears (not "employment_contract.pdf" example)
- ✅ Analysis shows real violations (not template examples)
- ✅ Timestamps reflect actual time (not hardcoded dates)
- ✅ File paths are real output paths
- ✅ Telemetry logs show actual tool invocations
- ✅ Markdown report contains actual extracted text

---

## Future Enhancements

### Short-term (Next 2-4 weeks)

1. **Custom Rule Evaluation**
   - Implement dispatcher for YAML `rules:` section
   - Add evaluators for `lease.*` rule types
   - Extend beyond 4 hardcoded compliance checks

2. **Enhanced Extraction**
   - Improve lease field extraction accuracy
   - Add support for more document types
   - Implement confidence scoring for extractions

3. **File Upload Fix**
   - Resolve LibreChat PDF upload issue
   - Test with various document types
   - Add file upload validation

### Medium-term (1-3 months)

4. **Multi-provider LLM Support**
   - Add OpenAI provider
   - Add Anthropic (Claude) provider
   - Add Google Gemini provider
   - Provider selection via configuration

5. **Advanced Classification**
   - Multi-label classification (hybrid contracts)
   - Confidence thresholds per document type
   - Custom classification models

6. **Batch Processing**
   - Analyze multiple documents in parallel
   - Batch report generation
   - Progress tracking for large batches

### Long-term (3-6 months)

7. **Machine Learning Enhancements**
   - Train custom classification models
   - Fine-tune extraction for specific industries
   - Active learning from user corrections

8. **Enterprise Features**
   - Multi-tenant support
   - Role-based access control
   - Audit logging
   - Compliance dashboards

9. **Integration Ecosystem**
   - REST API for external integrations
   - Webhook support for async processing
   - S3/Azure Blob storage integration
   - DocuSign integration

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 12+
- Node.js 18+ (for frontend)
- Tesseract OCR (for scanned PDF support)
- Ollama (for LLM analysis)

### Quick Start (MCP Server)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/contractextract.git
cd contractextract

# 2. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate      # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up PostgreSQL database
createdb contractextract

# 5. Configure environment
$env:DATABASE_URL="postgresql+psycopg2://postgres:password@localhost:5432/contractextract"

# 6. Initialize database
python -c "from infrastructure import init_db; init_db()"

# 7. Seed rule packs
python seed_database.py

# 8. Run MCP server
python mcp_server.py
```

### Quick Start (Frontend)

```bash
# 1. Navigate to frontend
cd frontend

# 2. Install dependencies
npm install

# 3. Start dev server
npm run dev

# Open browser to http://localhost:5173
```

### LibreChat Integration

```yaml
# Add to librechat.yaml
mcpServers:
  contractextract:
    command: "python"
    args: ["mcp_server.py"]
    cwd: "C:\\path\\to\\contractextract"
    initTimeout: 150000
    serverInstructions: true
```

---

## Support & Contact

- **Issues:** https://github.com/yourusername/contractextract/issues
- **Documentation:** See `CLAUDE.md` for development guide
- **Testing:** See `TEST_PLAN.md` for testing procedures

---

**Document Version:** 2.0
**Last Updated:** November 25, 2025
**Maintainer:** Noah C.
