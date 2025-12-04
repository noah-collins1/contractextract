# ContractExtract Frontend

React + TypeScript frontend for ContractExtract, using the HTTP Bridge to call MCP tools.

## Architecture

```
Frontend (React) → HTTP Bridge (FastAPI) → MCP Tool Handlers → Database
```

## Quick Start

### 1. Start the HTTP Bridge Server

```powershell
# In the project root
.\.venv\Scripts\Activate.ps1
python http_bridge.py
```

The HTTP bridge will start at: http://localhost:8000

### 2. Start the Frontend Dev Server

```powershell
# In the frontend directory
cd frontend
npm install
npm run dev
```

The frontend will start at: http://localhost:5173

## API Endpoints

The HTTP bridge exposes all MCP tools as REST endpoints:

- **GET** `/rule-packs/all` - List all rule packs
- **GET** `/rule-packs?status=active` - List active rule packs
- **GET** `/rule-packs/{pack_id}` - List versions for a pack
- **GET** `/rule-packs/{pack_id}/{version}` - Get pack details
- **GET** `/rule-packs/{pack_id}/{version}/yaml` - Get YAML content
- **POST** `/rule-packs/import-yaml` - Import YAML text
- **POST** `/rule-packs/upload-yaml` - Upload YAML file
- **PUT** `/rule-packs/{pack_id}/{version}` - Update draft pack
- **POST** `/rule-packs/{pack_id}/{version}:publish` - Publish pack
- **POST** `/rule-packs/{pack_id}/{version}:deprecate` - Deprecate pack
- **DELETE** `/rule-packs/{pack_id}/{version}` - Delete pack
- **POST** `/preview-run` - Analyze document (file upload)
- **GET** `/system-info` - System information

## Features

- **Dashboard**: View analysis statistics
- **Upload**: Drag & drop PDF analysis with rule pack selection
- **Rule Packs**: Manage rule packs (CRUD operations)
- **Documents**: View analysis history

## Tech Stack

- React 18
- TypeScript
- Vite
- React Router
- TanStack Query (React Query)
- Axios
- React Markdown

## Configuration

Edit `.env` to change the API URL:

```
VITE_API_BASE_URL=http://localhost:8000
```
