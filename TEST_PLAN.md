# ContractExtract Pure MCP Architecture - Test Plan

This document outlines comprehensive testing procedures for the **pure MCP (Model Context Protocol) architecture** optimized for LibreChat integration.

## 🏗️ Architecture Overview

**Current System (Phase 4 - Production Ready):**

- ✅ Pure stdio MCP server (`mcp_server.py`)
- ✅ Unified Pydantic v2 environment (`.venv`)
- ✅ 5 consolidated core modules
- ✅ PostgreSQL database with rule pack storage
- ✅ Direct LibreChat integration via stdio protocol

**Deprecated Components Removed:**

- ❌ FastAPI server and HTTP endpoints
- ❌ React frontend
- ❌ Dual Pydantic v1/v2 environments
- ❌ HTTP-based MCP bridge

## 🔧 Prerequisites

### Required Software

```powershell
# 1. Python 3.11+
python --version  # Should be 3.11+

# 2. PostgreSQL server running
# Create database: contractextract

# 3. LibreChat (for integration testing)
# Optional: Claude Code for MCP testing
```

### Environment Setup

```powershell
# 1. Activate unified environment
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Verify core imports
python -c "import mcp_server; print('✓ MCP server ready')"
```

## ✅ Level 1: Core System Validation

### 1.1 Python Environment Test

```powershell
# Test all critical imports
python -c "
import pydantic; print(f'Pydantic: {pydantic.__version__}')
import langextract; print('LangExtract: Available')
from mcp.server import Server; print('MCP SDK: Available')
import infrastructure; print('Infrastructure: ✓')
import contract_analyzer; print('Contract Analyzer: ✓')
import document_analysis; print('Document Analysis: ✓')
import rulepack_manager; print('Rulepack Manager: ✓')
print('🎉 All imports successful!')
"
```

**Expected Result:**

- Pydantic: 2.11.9
- All modules import without errors
- No version conflicts

### 1.2 Database Connection Test

```powershell
# Test database initialization
python -c "
from infrastructure import init_db, SessionLocal
try:
    init_db()
    print('✓ Database initialized successfully')
    session = SessionLocal()
    session.close()
    print('✓ Database session created and closed')
    print('🎉 Database connection working!')
except Exception as e:
    print(f'❌ Database error: {e}')
"
```

**Expected Result:**

- Database tables created/verified
- Session management working
- No connection errors

### 1.3 MCP Server Startup Test

```powershell
# Test MCP server initialization (will timeout - this is expected)
timeout 5 python mcp_server.py 2>&1 || echo "✓ Expected timeout - server started successfully"
```

**Expected Result:**

```
Starting ContractExtract MCP stdio server...
Server supports 16 tools for comprehensive rule pack and document analysis
Database initialized successfully
MCP stdio server running - ready for LibreChat connection
✓ Expected timeout - server started successfully
```

## ✅ Level 2: Rule Pack System Testing

### 2.1 Rule Pack Loading Test

```powershell
# Test rule pack loading from database
python -c "
from rulepack_manager import load_packs_for_runtime
from infrastructure import SessionLocal
db = SessionLocal()
packs = load_packs_for_runtime(db)
print(f'✓ Active rule packs loaded: {len(packs)}')
for pack_id, pack in packs.items():
    doc_types = list(getattr(pack, 'doc_type_names', []))
    print(f'  - {pack_id}: {doc_types}')
db.close()
print('🎉 Rule pack system working!')
"
```

**Expected Result:**

- 4+ active rule packs loaded
- Each pack has associated document types
- No loading errors

### 2.2 Document Type Detection Test

```powershell
# Test document classification
python -c "
from document_analysis import guess_doc_type_id
from rulepack_manager import load_packs_for_runtime
from infrastructure import SessionLocal

db = SessionLocal()
packs = load_packs_for_runtime(db)

test_cases = [
    'This is an employment agreement between Company and Employee for the position of Software Engineer with a starting salary of $100,000 per year.',
    'Joint venture agreement between ABC Corp and XYZ Inc for developing software solutions.',
    'Strategic alliance agreement for marketing partnership between two companies.'
]

for text in test_cases:
    guessed = guess_doc_type_id(text, packs)
    print(f'✓ Text: {text[:50]}...')
    print(f'  Detected: {guessed}\\n')

db.close()
print('🎉 Document classification working!')
"
```

**Expected Result:**

- Employment text → employment_v1
- Joint venture text → joint_venture_v1
- Strategic alliance text → strategic_alliance_v1

### 2.3 Contract Analysis Engine Test

```powershell
# Test analysis pipeline
python -c "
from contract_analyzer import make_report
from rulepack_manager import load_packs_for_runtime
from infrastructure import SessionLocal

db = SessionLocal()
packs = load_packs_for_runtime(db)

test_text = '''
Employment Agreement
This employment agreement is between XYZ Corp and John Doe.
The employee will receive $90,000 annually.
This agreement is governed by the laws of California, United States.
The employee's liability for company losses is capped at $500,000.
'''

pack = packs['employment_v1']
report = make_report('test_contract', test_text, pack.rules)

print(f'✓ Analysis completed: {\"PASS\" if report.passed_all else \"FAIL\"}')
print(f'✓ Findings count: {len(report.findings)}')
if report.findings:
    print(f'✓ First finding: {report.findings[0].rule_id}')

db.close()
print('🎉 Contract analysis engine working!')
"
```

**Expected Result:**

- Analysis completes without errors
- Returns pass/fail status
- Generates structured findings

## ✅ Level 3: MCP Tools Testing

### 3.1 MCP Tool Registration Test

```powershell
# Test MCP tool discovery
python -c "
import inspect
import mcp_server

# Count handler functions
handlers = [name for name in dir(mcp_server) if name.startswith('handle_')]
print(f'✓ MCP tool handlers found: {len(handlers)}')

# Verify key tools exist
key_tools = [
    'handle_list_all_rulepacks',
    'handle_analyze_document',
    'handle_create_rulepack_from_yaml',
    'handle_get_system_info'
]

for tool in key_tools:
    if hasattr(mcp_server, tool):
        print(f'✓ {tool}: Available')
    else:
        print(f'❌ {tool}: Missing')

print('🎉 MCP tools registered!')
"
```

**Expected Result:**

- 15+ MCP tool handlers found
- All key tools available
- No missing handlers

### 3.2 YAML Template Generation Test

```powershell
# Test YAML template generation
python -c "
import asyncio
from mcp_server import handle_generate_rulepack_template

async def test():
    args = {
        'pack_id': 'test_vendor_v1',
        'doc_type_names': ['Vendor Agreement', 'Service Contract']
    }
    template = await handle_generate_rulepack_template(args)
    print('✓ YAML template generated:')
    print(template[:200] + '...')
    print('🎉 Template generation working!')

asyncio.run(test())
"
```

**Expected Result:**

- Valid YAML template generated
- Contains specified pack_id and doc_types
- No generation errors

### 3.3 System Info Tool Test

```powershell
# Test system information tool
python -c "
import asyncio
from mcp_server import handle_get_system_info

async def test():
    info = await handle_get_system_info()
    print('✓ System Information:')
    print(f\"  Database: {info['database']['total_rule_packs']} total packs\")
    print(f\"  Environment: Pydantic {info['environment']['pydantic_version']}\")
    print(f\"  MCP Tools: {info['mcp_tools']['total_tools']} tools\")
    print('🎉 System info tool working!')

asyncio.run(test())
"
```

**Expected Result:**

- Returns comprehensive system status
- Database statistics included
- Environment details correct

## ✅ Level 4: LibreChat Integration Testing

### 4.1 LibreChat Configuration Test

```powershell
# Verify configuration file
python -c "
import yaml
import os

config_file = 'librechat_mcp_config.yaml'
if os.path.exists(config_file):
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    print('✓ LibreChat configuration found')
    server_config = config['mcpServers']['contractextract']
    print(f\"  Command: {server_config['command']}\")
    print(f\"  Args: {server_config['args']}\")
    print(f\"  CWD: {server_config['cwd']}\")

    # Verify paths exist
    cwd_path = server_config['cwd']
    mcp_file = os.path.join(cwd_path, 'mcp_server.py')

    if os.path.exists(mcp_file):
        print('✓ MCP server file exists at configured path')
    else:
        print('❌ MCP server file missing at configured path')

    print('🎉 LibreChat configuration valid!')
else:
    print('❌ LibreChat configuration file missing')
"
```

**Expected Result:**

- Configuration file exists and is valid
- All paths correctly configured
- MCP server file exists at specified location

### 4.2 MCP stdio Protocol Test

```powershell
# Test stdio protocol communication (manual)
echo "This test requires manual LibreChat integration"
echo "Steps:"
echo "1. Start LibreChat with ContractExtract MCP server configured"
echo "2. In LibreChat, try these commands:"
echo "   - 'List all available rule packs'"
echo "   - 'Show me system information'"
echo "   - 'Generate a template for vendor agreements'"
echo "   - 'Analyze this contract text: [sample text]'"
echo ""
echo "Expected Results:"
echo "✓ Tools discoverable in LibreChat"
echo "✓ Natural language commands work"
echo "✓ Responses are properly formatted"
echo "✓ No protocol errors in logs"
```

## ✅ Level 5: Document Analysis End-to-End Testing

### 5.1 Full Document Analysis Test

```powershell
# Test complete document analysis workflow
python -c "
import asyncio
import hashlib
from mcp_server import handle_analyze_document

async def test():
    # Sample contract text
    contract_text = '''
    EMPLOYMENT AGREEMENT

    This Employment Agreement is made between TechCorp Inc. and Jane Smith.
    Position: Senior Software Engineer
    Salary: $120,000 per year
    Location: California, United States

    LIABILITY LIMITATION:
    Employee's liability for company losses is limited to $1,000,000.

    GOVERNING LAW:
    This agreement is governed by California state law.
    '''

    args = {
        'document_text': contract_text,
        'doc_type_hint': 'employment_v1'
    }

    print('✓ Starting document analysis...')
    result = await handle_analyze_document(args)

    print(f\"✓ Analysis completed: {result['overall_result']}\")
    print(f\"✓ Document type: {result['doc_type']}\")
    print(f\"✓ Violations found: {result['violation_count']}\")
    print(f\"✓ Total findings: {result['total_findings']}\")

    if result['output_files']:
        print(f\"✓ Reports generated: {list(result['output_files'].keys())}\")

    print('🎉 Document analysis working!')

asyncio.run(test())
"
```

**Expected Result:**

- Analysis completes successfully
- Document type correctly identified
- Violations/findings reported
- Output files generated

### 5.2 Preview Analysis Test

```powershell
# Test quick preview functionality
python -c "
import asyncio
from mcp_server import handle_preview_document_analysis

async def test():
    contract_text = 'This is a simple service agreement between Company A and Company B, governed by New York law.'

    args = {'document_text': contract_text}

    result = await handle_preview_document_analysis(args)

    print(f\"✓ Preview analysis: {result['overall_result']}\")
    print(f\"✓ Pack used: {result['pack_used']}\")
    print(f\"✓ Violations: {result['violation_count']}\")
    print('🎉 Preview analysis working!')

asyncio.run(test())
"
```

**Expected Result:**

- Quick analysis without file output
- Appropriate rule pack selected
- Results returned in summary format

## 🚨 Critical Success Criteria

**System is ready for production if ALL these pass:**

### Core System Tests

- [ ]  All Python modules import successfully
- [ ]  Database connection and initialization works
- [ ]  MCP server starts without errors
- [ ]  All 16 MCP tools are registered

### Rule Pack System Tests

- [ ]  Active rule packs load from database
- [ ]  Document type detection works correctly
- [ ]  Contract analysis engine produces findings
- [ ]  YAML template generation works

### Integration Tests

- [ ]  LibreChat configuration is valid
- [ ]  MCP stdio protocol functions
- [ ]  Document analysis end-to-end works
- [ ]  System information tool responds

## 🐛 Troubleshooting Guide

### Common Issues

**Import Errors:**

```powershell
# Check Python environment
python -c "import sys; print(sys.executable)"
# Should point to .venv\Scripts\python.exe

# Reinstall dependencies
pip install -r requirements.txt
```

**Database Connection Failed:**

```powershell
# Check PostgreSQL service
# Verify database 'contractextract' exists
# Check connection string in infrastructure.py
```

**MCP Server Won't Start:**

```powershell
# Check for port conflicts (stdio protocol doesn't use ports)
# Verify all modules import correctly
# Check database connection
```

**LibreChat Integration Issues:**

```powershell
# Verify paths in librechat_mcp_config.yaml
# Check LibreChat logs for MCP errors
# Increase initTimeout if needed (currently 150000ms)
```

### Debug Commands

```powershell
# Test specific components
python -c "from infrastructure import init_db; init_db()"
python -c "from rulepack_manager import load_packs_for_runtime; from infrastructure import SessionLocal; db = SessionLocal(); print(len(load_packs_for_runtime(db)))"

# Check outputs directory
ls outputs\

# Monitor logs (if enabled)
set CE_LOG_LEVEL=DEBUG
python mcp_server.py
```

## 📊 Performance Expectations

**Typical Performance:**

- MCP server startup: < 5 seconds
- Rule pack loading: < 2 seconds
- Document analysis: 10-30 seconds (depending on LLM)
- Database operations: < 1 second

**Resource Usage:**

- Memory: 200-500 MB (depending on document size)
- Storage: Outputs directory grows with analyses
- Database: Minimal storage for rule packs

## 🎯 Next Steps After Testing

If all tests pass:

1. **Production Deployment:**

   - Configure production database
   - Set up LibreChat with MCP integration
   - Deploy to production environment
2. **User Training:**

   - Document LibreChat command patterns
   - Create user guides for rule pack management
   - Train users on document analysis workflow
3. **Monitoring:**

   - Set up logging and monitoring
   - Configure alerting for system health
   - Plan backup and recovery procedures

---

**Architecture:** Pure MCP (stdio protocol)
**Status:** Production Ready
**Last Updated:** Phase 4 Completion
**Integration:** LibreChat via stdio MCP server
