# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the **ContractExtract Pure MCP Architecture**.

## Quick Start

### Production MCP Server
```bash
# Activate environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run pure stdio MCP server
python mcp_server.py
```

### LibreChat Integration
```yaml
# Add to librechat.yaml
mcpServers:
  contractextract:
    command: "python"
    args: ["mcp_server.py"]
    cwd: "C:\\Users\\noahc\\PycharmProjects\\langextract"
    initTimeout: 150000
    serverInstructions: true
```

## Architecture Overview

**ContractExtract** is a **pure MCP (Model Context Protocol) server** that provides contract analysis and compliance checking directly to LibreChat via stdio protocol.

### Core Architecture

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

### Key Components

**Pure MCP Server** (`mcp_server.py`):
- 16 MCP tools for comprehensive contract analysis
- Direct stdio communication with LibreChat
- Async/await architecture for optimal performance
- No HTTP overhead - pure process communication

**Consolidated Modules**:
- `infrastructure.py`: Configuration, database, schemas, telemetry
- `contract_analyzer.py`: Analysis engine with LLM integration
- `document_analysis.py`: PDF processing and document classification
- `rulepack_manager.py`: Rule pack storage and lifecycle management

**Database Layer**:
- PostgreSQL with versioned YAML rule packs
- Rule pack lifecycle: draft → active → deprecated
- Support for custom rule extensions and schema evolution

### MCP Tools Available

#### Rule Pack Management (8 tools)
- `list_all_rulepacks`: List all rule packs with status
- `list_active_rulepacks`: List only active rule packs
- `get_rulepack_details`: Get detailed rule pack information
- `get_rulepack_yaml`: Retrieve raw YAML content
- `list_rulepack_versions`: List all versions of a rule pack
- `create_rulepack_from_yaml`: Create new rule pack from YAML
- `update_rulepack_yaml`: Update draft rule pack
- `publish_rulepack`: Publish draft to active status

#### Document Analysis (2 tools)
- `analyze_document`: Full contract analysis with reporting
- `preview_document_analysis`: Quick analysis without file output

#### Utilities (6 tools)
- `generate_rulepack_template`: Generate YAML template
- `validate_rulepack_yaml`: Validate YAML before import
- `get_system_info`: System status and diagnostics
- `deprecate_rulepack`: Deprecate active rule packs
- `delete_rulepack`: Delete rule packs (with safety checks)

## Development Workflow

### Environment Setup
```bash
# Single unified environment (Pydantic v2)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Database setup (PostgreSQL required)
# Create database: contractextract
# Tables auto-created on first run
```

### Running the MCP Server
```bash
# Development mode
python mcp_server.py

# Production mode (with LibreChat)
# Configure librechat.yaml and start LibreChat
```

### Testing MCP Tools
```bash
# Test imports and startup
python -c "import mcp_server; print('MCP server ready')"

# Test database connection
python -c "from infrastructure import init_db; init_db(); print('Database connected')"

# Test consolidated modules
python -c "from contract_analyzer import make_report; print('Analysis engine ready')"
```

## Database Configuration

### PostgreSQL Setup
```sql
-- Create database
CREATE DATABASE contractextract;

-- Connection string (in environment or infrastructure.py)
postgresql+psycopg2://postgres:password@localhost:5432/contractextract
```

### Rule Pack Storage
- **Schema**: Versioned YAML rule packs in PostgreSQL
- **Lifecycle**: draft → active → deprecated
- **Extensions**: Support for custom rule types and metadata
- **Validation**: Automatic schema compliance checking

### Exposing PostgreSQL Port (Optional - For Local Development)

If you want to access LibreChat's PostgreSQL from your local machine (useful for debugging, pgAdmin, seeding database, etc.), you can expose the port.

**Steps:**

1. **Create or edit `docker-compose.override.yml`** in your LibreChat directory:

```yaml
# docker-compose.override.yml
version: '3.4'

services:
  contractextract-db:
    ports:
      - "5433:5432"  # Expose on port 5433 to avoid conflict with local PostgreSQL
```

Note: Using port `5433` to avoid conflicts if you have PostgreSQL running locally on `5432`.

2. **Restart LibreChat:**

```powershell
docker-compose down
docker-compose up -d
```

3. **Verify port is exposed:**

```powershell
docker ps | findstr contractextract-db
# Should show: 0.0.0.0:5433->5432/tcp
```

4. **Connect from local machine:**

```powershell
# Example: Seed database from local machine
cd C:\Users\noahc\PycharmProjects\langextract
.\.venv\Scripts\Activate.ps1

# Set DATABASE_URL to exposed port
$env:DATABASE_URL="postgresql+psycopg2://postgres:contractextract_pass@localhost:5433/contractextract"

# Run seed or other database scripts
python seed_database.py
```

5. **Connect with pgAdmin (Optional):**
   - **Host:** localhost
   - **Port:** 5433
   - **Database:** contractextract
   - **User:** postgres
   - **Password:** contractextract_pass

## File Structure (Post-Consolidation)

```
contractextract/
├── mcp_server.py                   # Pure stdio MCP server (959 lines)
├── infrastructure.py               # Config/DB/schemas/telemetry (267 lines)
├── contract_analyzer.py            # Analysis engine + LLM (590 lines)
├── document_analysis.py            # Document processing pipeline (514 lines)
├── rulepack_manager.py             # Rule pack data access layer (313 lines)
├── requirements.txt                # Unified Pydantic v2 dependencies
├── librechat_mcp_config.yaml       # LibreChat configuration examples
├── CLAUDE.md                       # This documentation
├── .venv/                          # Single unified Python environment
├── rules_packs/                    # YAML rule definitions (8 files)
├── data/                           # Test PDF documents
├── outputs/                        # Generated analysis reports
└── archive/                        # Legacy reference files
```

## Rule Pack Development

### YAML Schema v1.0
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
  LLM analysis prompt for this rule pack

examples:
  - text: "Sample contract text"
    extractions: [...]

notes: "Documentation for this rule pack"
```

### Rule Pack Lifecycle
1. **Create**: `create_rulepack_from_yaml` → draft status
2. **Edit**: `update_rulepack_yaml` (drafts only)
3. **Validate**: `validate_rulepack_yaml`
4. **Publish**: `publish_rulepack` → active status
5. **Deprecate**: `deprecate_rulepack` when no longer needed

## Technology Stack

### Core Dependencies
- **Python 3.11+** with unified virtual environment
- **Pydantic v2.11.9** for data validation and serialization
- **LangExtract 1.0.9** for LLM-powered information extraction
- **MCP SDK 1.14.1** for LibreChat integration
- **PostgreSQL** for rule pack storage
- **SQLAlchemy 2.0** for database ORM

### Document Processing
- **pdfplumber** for PDF text extraction with page preservation
- **Custom citation mapping** with page/line number tracking
- **Document type classification** with rules-based + LLM fallback

### LLM Integration
- **Ollama** as default local LLM provider
- **Configurable providers** via LLM factory pattern
- **Budget controls** and timeout protection

## Deployment Options

### Development (Windows)
```yaml
mcpServers:
  contractextract:
    command: "python"
    args: ["mcp_server.py"]
    cwd: "C:\\Users\\username\\PycharmProjects\\langextract"
```

### Production (Linux)
```yaml
mcpServers:
  contractextract:
    command: "/opt/contractextract/.venv/bin/python"
    args: ["mcp_server.py"]
    cwd: "/opt/contractextract"
    env:
      DATABASE_URL: "postgresql://user:pass@db:5432/contractextract"
```

### Docker
```yaml
mcpServers:
  contractextract:
    command: "python"
    args: ["mcp_server.py"]
    cwd: "/app/contractextract"
    env:
      DATABASE_URL: "postgresql://postgres:password@db:5432/contractextract"
```

## Performance Characteristics

### Optimizations
- **stdio protocol**: Direct process communication (no HTTP overhead)
- **Consolidated modules**: Reduced import overhead and complexity
- **Unified environment**: Single dependency tree
- **Database connection pooling**: Efficient PostgreSQL usage
- **LLM budget controls**: Token limits and timeout protection

### Scalability
- **Horizontal**: Multiple MCP server instances
- **Vertical**: Async/await architecture for concurrent requests
- **Storage**: PostgreSQL handles large rule pack collections
- **Processing**: Configurable parallelism for document analysis

## Troubleshooting

### Common Issues
```bash
# Import errors
python -c "import mcp_server" # Should succeed

# Database connection
python -c "from infrastructure import init_db; init_db()" # Should connect

# MCP SDK compatibility
python -c "from mcp.server import Server" # Should import

# Pydantic version
python -c "import pydantic; print(pydantic.__version__)" # Should be 2.11.9
```

### LibreChat Integration
- **Check stdio protocol**: Ensure LibreChat can spawn processes
- **Verify paths**: Absolute paths in `cwd` configuration
- **Timeout settings**: Increase `initTimeout` for slow startup
- **Logging**: Enable debug logging with `CE_LOG_LEVEL=DEBUG`

## Important Notes

### Architecture Evolution
This system has evolved through multiple phases:
- **Phase 1**: Separate FastAPI + React architecture
- **Phase 2**: File consolidation (23 files → 8 files)
- **Phase 3**: Pure MCP migration (HTTP → stdio)
- **Phase 4**: Final cleanup and documentation

### Deprecated Approaches
- ❌ **FastAPI + HTTP MCP**: Replaced by pure stdio
- ❌ **Dual Pydantic environments**: Unified on v2
- ❌ **React frontend**: LibreChat provides UI
- ❌ **CLI tools**: MCP tools replace CLI interface

### Production Ready
- ✅ **Single environment**: Simplified deployment
- ✅ **Pure MCP protocol**: Optimal LibreChat integration
- ✅ **Consolidated codebase**: Easy maintenance
- ✅ **PostgreSQL storage**: Production database
- ✅ **Comprehensive tooling**: 16 MCP tools for complete workflow

---

## 🔍 Known Issues & Testing Tasks (To Be Addressed)

### **Critical: PDF File Upload Investigation**

**Issue Discovered:** 2025-10-03
**Status:** 🔴 Needs Investigation

#### Problem Description
When uploading a real PDF to LibreChat and requesting analysis via the ContractExtract CLI agent, the system appears to either:
1. **Hallucinate** example data instead of processing the actual PDF
2. **Use template/example responses** from the CLI prompt instead of real analysis
3. **File upload mechanism failing** between LibreChat and MCP tools

#### Evidence
User uploaded actual PDF, but response contained:
- Generic example data: `employment_contract.pdf`
- Template violation descriptions matching CLI prompt examples
- Fixed dates: `2025-01-15 14:30:22` (not current timestamp)
- Example violations: "Delaware jurisdiction", "14 days vs 30 days", etc.
- Placeholder file paths: `C:\\...\\report.md`

**This suggests the LLM is responding with the example from the CLI prompt rather than invoking the actual MCP tool.**

#### Possible Root Causes

**1. LibreChat File Handling Conflicts**
- ContractExtract and RAGsearch both require file uploads
- Potential conflict in MCP file attachment handling
- LibreChat may not properly pass file references to MCP tools
- Need to verify: Does MCP protocol support file uploads via stdio?

**2. CLI Prompt Too Complex**
- The CONTRACTEXTRACT_CLI_PROMPT.md may be too detailed
- Example outputs in prompt causing LLM to hallucinate instead of using tools
- LLM generating responses from examples rather than making tool calls
- Need to simplify prompt and reduce example verbosity

**3. MCP Tool Parameter Handling**
- `analyze_document` tool expects file path parameter
- LibreChat may not be converting file uploads to accessible paths
- File might be uploaded but path not passed to MCP server
- Need to verify parameter passing from LibreChat → MCP server

**4. Agent vs Direct Tool Call Confusion**
- Using agent with instructions vs direct tool calls
- Agent may prefer generating text over making tool calls
- Need to test direct MCP tool invocation without agent wrapper

#### Testing Tasks (Priority Order)

**🔴 HIGH PRIORITY - File Upload Verification**
1. **Test direct MCP tool call** (no CLI agent)
   - Upload PDF in LibreChat
   - Directly invoke `analyze_document` tool
   - Verify file path is received by mcp_server.py
   - Check telemetry logs for actual tool invocation

2. **Verify MCP stdio file handling**
   - Research: Can MCP stdio protocol handle file uploads?
   - Check MCP SDK documentation for file attachment support
   - Test with MCP Inspector tool
   - Verify LibreChat passes file references correctly

3. **RAGsearch conflict investigation**
   - Disable RAGsearch temporarily
   - Test ContractExtract file upload alone
   - Check if multiple MCP servers with file upload cause conflicts
   - Review LibreChat logs for file handling errors

**🟡 MEDIUM PRIORITY - Prompt Engineering**
4. **Simplify CLI prompt**
   - Remove or reduce example outputs
   - Make examples more clearly marked as templates
   - Add explicit instructions: "DO NOT generate example data"
   - Test with minimal prompt (just tool descriptions)

5. **Test each MCP tool individually**
   - `list_all_rulepacks` - Simple, no file needed
   - `list_active_rulepacks` - Simple, no file needed
   - `get_rulepack_details` - Takes string parameter
   - `get_system_info` - No parameters
   - `analyze_document` - **Critical** - Takes file path
   - Document which tools work and which fail

6. **Verify markdown report integration**
   - Confirm `markdown_report` field is populated
   - Check if LLM displays actual report vs example
   - Verify file paths in output are real, not placeholders

**🟢 LOW PRIORITY - Agent Optimization**
7. **Agent instruction refinement**
   - Test without CLI prompt wrapper
   - Use simpler "analyze this document" instruction
   - Compare agent behavior vs direct tool calls
   - Optimize for tool usage over text generation

#### Debug Commands

```powershell
# Manual MCP server testing
cd C:\Users\noahc\PycharmProjects\langextract
.\.venv\Scripts\Activate.ps1
python mcp_server.py
# Watch for actual tool calls vs hallucinations

# Check telemetry logs
python -c "from infrastructure import get_logger; logger = get_logger(); logger.info('Test')"

# Test file path handling
python -c "from document_analysis import extract_text_with_pages; print(extract_text_with_pages('data/test.pdf'))"

# Verify database has real rule packs (not examples)
python -c "from rulepack_manager import list_active_rulepacks; import json; print(json.dumps(list_active_rulepacks(), indent=2))"
```

#### Research Tasks

1. **MCP Protocol File Support**
   - Review MCP specification for file attachment handling
   - Check if stdio protocol supports binary file transfer
   - Investigate LibreChat MCP file upload implementation
   - Test with MCP Inspector tool

2. **LibreChat Multiple MCP Servers**
   - Document file upload handling with multiple MCP servers
   - Check if RAGsearch and ContractExtract conflict
   - Review LibreChat source code for file routing logic

3. **Agent Behavior Analysis**
   - Test same prompt with different LLM models
   - Compare tool usage rates
   - Identify if specific models prefer hallucination over tools

#### Success Criteria

**✅ File upload working when:**
- Upload real PDF → see actual filename (not "employment_contract.pdf")
- Analysis shows real content violations (not template examples)
- Timestamps reflect actual analysis time (not 2025-01-15 14:30:22)
- File paths are real output paths (not `C:\\...\\report.md`)
- Telemetry logs show actual `analyze_document` tool call
- Markdown report contains actual extracted text from PDF

#### Notes
- This is critical for production use - template responses are unacceptable
- May need to redesign CLI prompt approach entirely
- Consider direct tool invocation without agent wrapper
- File upload is core functionality - must work reliably

---

**This architecture provides a production-ready, high-performance contract analysis system optimized for LibreChat integration via pure MCP protocol.**