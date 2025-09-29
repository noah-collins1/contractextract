# Changelog

All notable changes to the ContractExtract project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Enhanced LLM rationale generation
- Multi-language document support
- Advanced citation highlighting
- Export compliance dashboards
- Machine learning model integration

---

## [1.2.1] - 2025-01-XX (Current Session)

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

### Technical Improvements
- **Development Workflow**
  - Added comprehensive validation script for all YAML rule packs
  - Created batch fixing utility for YAML standardization
  - Improved documentation in both README.md and CLAUDE.md
  - Enhanced file organization with clear template structure

- **Code Quality**
  - Better separation of concerns in evaluation pipeline
  - Improved error handling throughout the system
  - Enhanced logging for debugging and monitoring
  - Consistent code formatting and structure

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

### Technical
- **Environment Management**
  - Separated Pydantic v1/v2 environments for compatibility
  - Created helper scripts for environment switching
  - Enhanced development commands and documentation

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
Each commit should follow this format for tracking:
```
type(scope): description

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Version Numbering
- **Major (X.0.0)**: Breaking changes, major new features
- **Minor (X.Y.0)**: New features, backward compatible
- **Patch (X.Y.Z)**: Bug fixes, improvements, patches

### Key Git Branches
- `master`: Main development branch
- Feature branches: For new capabilities and improvements
- Release branches: For version preparation and testing

### Recent Development Sessions
1. **API Enhancement & LLM Improvements** (Current)
   - Enhanced API response tracking with SHA1 hashing
   - Improved LLM explanation system with executive summaries
   - Fixed document processing uniqueness issues

2. **YAML Schema Standardization** (Current)
   - Created standardized schema v1.0 for all rule packs
   - Fixed YAML syntax errors across all files
   - Added comprehensive validation tooling

3. **LibreChat MCP Integration** (v1.2.0)
   - Implemented 16 MCP tools for full functionality
   - Created dual environment support for Pydantic compatibility
   - Enhanced development workflow and documentation

4. **Frontend Development** (v1.1.0)
   - Built React/TypeScript frontend application
   - Enhanced API with comprehensive endpoints
   - Added real-time processing capabilities

5. **Initial Development** (v1.0.0)
   - Core contract analysis engine
   - Database integration and rule pack system
   - LLM integration and citation tracking

---

**Maintained by:** Noah Collins, Trey Drake
**Repository:** Private enterprise contract analysis system
**Documentation:** See [README.md](./README.md) and [CLAUDE.md](./CLAUDE.md)