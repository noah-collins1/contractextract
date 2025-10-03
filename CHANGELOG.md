# Changelog

All notable changes to the ContractExtract project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Multi-language document support (Spanish, French, German)
- Enhanced citation highlighting with visual markers in reports
- Export compliance dashboards with analytics
- Advanced LLM rationale generation with chain-of-thought
- Machine learning model integration for auto-classification

---

## [1.3.0] - 2025-01-XX (Phase 4 - Pure MCP Architecture)

### Added
- **🚀 Pure Stdio MCP Protocol**
  - Direct stdio communication with LibreChat (no HTTP overhead)
  - Single `mcp_server.py` file (959 lines) replacing entire MCP directory
  - Async/await architecture for optimal performance
  - Automatic process management via LibreChat

- **📦 File Consolidation (23 → 5 Core Modules)**
  - `infrastructure.py` - Configuration, database, schemas, telemetry (267 lines)
  - `contract_analyzer.py` - Analysis engine with LLM integration (590 lines)
  - `document_analysis.py` - PDF processing and document classification (514 lines)
  - `rulepack_manager.py` - Rule pack storage and lifecycle management (313 lines)
  - `mcp_server.py` - Pure stdio MCP server with 16 tools (959 lines)

- **✨ Markdown Report Integration**
  - `analyze_document` tool now returns full markdown report in response
  - LibreChat can display formatted reports directly in chat
  - Automatic markdown content extraction after file save
  - New `markdown_report` field in JSON responses

- **📝 Enhanced Documentation**
  - Complete README.md rewrite with table of contents
  - Documentation index with audience targeting
  - Updated CLAUDE.md for pure MCP architecture
  - Phase 4 consolidation tracking in FILE_MANIFEST.md
  - Enhanced CLI prompt for LibreChat agent integration

### Changed
- **🏗️ Architecture Simplification**
  - Removed FastAPI HTTP server (replaced by pure MCP)
  - Removed React frontend (LibreChat provides UI)
  - Unified Pydantic v2 environment (removed v1/v2 split)
  - Eliminated HTTP MCP protocol (stdio only)
  - Removed bridge services (no longer needed)

- **⚙️ Environment & Dependencies**
  - Single `requirements.txt` (Pydantic v2 + MCP SDK 1.14.1)
  - Removed `requirements-v1.txt` and `requirements-v2.txt`
  - Simplified virtual environment setup (`.venv` only)
  - Updated all dependencies to latest stable versions

- **📋 MCP Tools Enhancement**
  - Consolidated tool implementations into single file
  - Improved error handling and logging across all tools
  - Enhanced parameter validation and type safety
  - Better integration with consolidated modules

### Removed
- **Deprecated Components**
  - ❌ `app.py` - FastAPI HTTP server
  - ❌ `db.py` - Separate database module
  - ❌ `models_rulepack.py` - SQLAlchemy models
  - ❌ `schemas.py` - Pydantic schemas
  - ❌ `evaluator.py` - Evaluation engine
  - ❌ `ingest.py` - PDF ingestion
  - ❌ `doc_type.py` - Document classification
  - ❌ `rulepack_repo.py`, `rulepack_loader.py`, `rulepack_dtos.py` - Rule pack management
  - ❌ `yaml_importer.py` - YAML import utilities
  - ❌ `llm_factory.py`, `llm_provider.py` - LLM abstraction
  - ❌ `citation_mapper.py` - Citation utilities
  - ❌ `telemetry.py`, `settings.py` - Configuration files
  - ❌ `bridge_client.py`, `langextract_service.py` - Bridge services
  - ❌ `mcp_server/` directory - All MCP-related subdirectory files
  - ❌ `front/` directory - React frontend application
  - ❌ `librechat/` directory - Moved to config files

### Fixed
- **Performance & Reliability**
  - Eliminated HTTP overhead with direct stdio communication
  - Reduced import complexity and startup time
  - Improved error handling across consolidated modules
  - Better resource management with single process model

### Migration Notes
**Breaking Changes:**
- FastAPI HTTP endpoints no longer available
- React frontend removed (use LibreChat UI)
- Dual environment setup replaced by single `.venv`
- MCP configuration changed from HTTP to stdio protocol

**Migration Path:**
1. Delete old virtual environments (`.venv-v1`, `.venv-v2`)
2. Create new `.venv` with `requirements.txt`
3. Update `librechat.yaml` to use stdio protocol
4. Remove references to `app.py` in startup scripts
5. Use LibreChat UI instead of React frontend

---

## [1.2.1] - 2025-01-XX (YAML Schema & LLM Enhancements)

### Added
- **YAML Rule Pack Schema Standardization (v1.0)**
  - Standardized schema structure with required and optional fields
  - Schema version tracking system (`schema_version: "1.0"`)
  - Comprehensive YAML validation script (`validate_yaml_rulepacks.py`)
  - Standard template file (`_TEMPLATE.yml`) for new rule pack creation
  - Support for extensions and custom fields with schema validation

- **Enhanced API Response Tracking**
  - SHA1 hashing for document content verification
  - Enhanced `/preview-run` endpoint with metadata response
  - Structured logging with filename, SHA1, pack ID, and results
  - Metadata fields: `filename`, `sha1`, `selected_pack_id`, `pass_fail`

- **Improved LLM Explanation System**
  - Executive summary section for failed compliance reports
  - Top 3 failing rules highlighting with risk assessment
  - Enhanced LLM integration with better error handling
  - Cleaner prompt formatting focused on actionable insights
  - Better filtering to avoid processing status findings

- **Report Generation Enhancements**
  - Executive summary automatically prepended to failed reports
  - Improved citation handling with better quote truncation
  - Enhanced markdown rendering consistency across API and batch processing
  - Status finding management improvements

### Changed
- **Updated All Rule Packs to Schema v1.0**
  - `strategic_alliance.yml` - Reference implementation with notes
  - `employment.yml` - Employment contract rules with schema compliance
  - `noncompete.yml` - Non-compete agreement rules with proper formatting
  - `ip_agreement.yml` - IP assignment rules with schema compliance
  - `joint_venture.yml` - Joint venture rules with standardized structure
  - `promotion.yml` - Marketing promotion rules with validation
  - `servicing.yml` - Service agreement rules with proper schema

- **Enhanced YAML Importer**
  - Added support for `schema_version` field processing
  - Added support for `extensions` and `extensions_schema` fields
  - Improved backward compatibility with default v1.0 schema

### Fixed
- **YAML Syntax Errors**
  - Fixed incorrectly quoted field names in rules sections
  - Corrected label formatting in examples sections
  - Resolved YAML parsing errors across all rule pack files
  - Fixed string formatting inconsistencies

- **LLM Explanation Robustness**
  - Better error handling for provider loading and import issues
  - More robust handling of empty or failed LLM responses
  - Improved status reporting for explanation generation
  - Enhanced exception handling in LLM processing pipeline

---

## [1.2.0] - 2025-01-XX (LibreChat MCP Integration)

### Added
- **Complete LibreChat MCP Integration**
  - 16 comprehensive MCP tools for rule pack lifecycle management
  - JSON-RPC MCP protocol implementation
  - Real-time rule pack creation/editing via natural language
  - Document analysis directly in LibreChat conversations

- **MCP Tools Suite**
  - Rule Pack Management: `list_all_rulepacks`, `list_active_rulepacks`, `get_rulepack_details`
  - Rule Pack Creation: `create_rulepack_from_yaml`, `update_rulepack_yaml`, `publish_rulepack`
  - Document Analysis: `analyze_document`, `preview_document_analysis`
  - Utilities: `generate_rulepack_template`, `validate_rulepack_yaml`, `get_system_info`

- **Dual Environment Support**
  - Pydantic v2 environment (`.venv-v2`) for FastAPI + MCP
  - Pydantic v1 environment (`.venv-v1`) for LangExtract compatibility
  - Optional HTTP bridge for v1/v2 integration

### Changed
- **Architecture Updates**
  - Added `mcp_server/` directory with MCP integration
  - Enhanced FastAPI app with MCP endpoint at `/mcp`
  - Updated database schema to support MCP operations

---

## [1.1.0] - 2024-XX-XX (React Frontend & API Enhancement)

### Added
- **React Frontend Application**
  - Modern React/TypeScript frontend with Vite
  - Rule pack management interface
  - Document upload and analysis capabilities
  - Real-time processing status updates

- **Enhanced API Endpoints**
  - Comprehensive REST API for rule pack CRUD operations
  - File upload and processing endpoints
  - Swagger/OpenAPI documentation at `/docs`
  - CORS support for frontend development

### Changed
- **Database Schema**
  - Enhanced `rule_packs` table with versioning support
  - Added lifecycle management (draft → active → deprecated)
  - Improved indexing and query performance

---

## [1.0.0] - 2024-XX-XX (Initial Release)

### Added
- **Core Contract Analysis Engine**
  - PDF ingestion via pdfplumber
  - Document type detection using regex matching
  - Rule-based evaluation pipeline
  - Structured output generation (JSON + Markdown)

- **Database Integration**
  - PostgreSQL with SQLAlchemy ORM
  - Rule pack storage and versioning
  - Configuration-driven evaluation

- **LLM Integration**
  - Optional LLM rationales for failed findings
  - Configurable LLM provider support
  - Few-shot learning with examples

- **Key Features**
  - Liability cap compliance checking
  - Contract value threshold validation
  - Fraud clause detection
  - Jurisdiction allowlist compliance
  - Citation tracking with character-level positioning

### Technical
- **Architecture**
  - FastAPI backend with Python 3.11
  - PostgreSQL database
  - Modular rule pack system
  - Extensible evaluation engine

- **Configuration**
  - YAML-based rule pack definitions
  - Environment variable configuration
  - Batch processing capabilities

---

## Development Process

### Commit Message Format
```
type(scope): description

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Version Numbering
- **Major (X.0.0)**: Breaking changes, major architecture shifts
- **Minor (X.Y.0)**: New features, backward compatible enhancements
- **Patch (X.Y.Z)**: Bug fixes, improvements, documentation

### Key Milestones

#### **Phase 4 (v1.3.0)** - Pure MCP Architecture
- File consolidation: 23 → 5 core modules
- Stdio protocol migration
- Markdown report integration
- Complete documentation rewrite

#### **Phase 3 (v1.2.1)** - Schema & Quality
- YAML schema standardization v1.0
- LLM explanation enhancements
- Report generation improvements

#### **Phase 2 (v1.2.0)** - LibreChat Integration
- 16 MCP tools implementation
- Dual environment setup
- Natural language rule pack editing

#### **Phase 1 (v1.0-1.1)** - Foundation
- Core analysis engine
- React frontend
- Database integration

---

## Recent Development Sessions

### **Session 5: Phase 4 Consolidation & Documentation** (Current)
- Consolidated 23 files into 5 core modules
- Migrated to pure stdio MCP protocol
- Added markdown report integration
- Rewrote all documentation for new architecture
- Updated LibreChat CLI prompt for agent integration

### **Session 4: YAML Schema & LLM Enhancements**
- Standardized YAML schema to v1.0
- Enhanced LLM explanation system
- Added executive summaries to reports
- Fixed YAML syntax errors across all rule packs

### **Session 3: MCP Integration**
- Implemented 16 MCP tools
- Created dual environment setup
- Built HTTP MCP endpoint
- Enhanced rule pack lifecycle management

### **Session 2: Frontend Development**
- Built React/TypeScript frontend
- Enhanced API with comprehensive endpoints
- Added real-time processing updates

### **Session 1: Initial Development**
- Core contract analysis engine
- Database integration with PostgreSQL
- LLM integration for explanations

---

**Maintained by:** Noah Collins, Trey Drake
**Repository:** Private enterprise contract analysis system
**Documentation:** See [README.md](./README.md) and [CLAUDE.md](./CLAUDE.md)