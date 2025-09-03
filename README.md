# LangExtract Contract Evaluator

A **FastAPI-based contract analysis service** with a companion **React frontend**.  
The system ingests PDFs, runs them through a configurable rule-based pipeline, and outputs **compliance reports** in Markdown and JSON.  

Rules are stored as **versioned YAML “rule packs”** in Postgres, so behavior is fully data-driven. Optional LLM rationales can enrich findings.

---

## ✨ Features

- **PDF ingestion** via [pdfplumber](https://github.com/jsvine/pdfplumber).
- **Document type detection** (regex vs. `doc_type_names` from rule packs).
- **Rule packs in Postgres**: draft → active → deprecated lifecycle.
- **Evaluation pipeline**:
  - Liability caps
  - Contract value thresholds
  - Fraud clauses
  - Jurisdiction allowlist
  - Extensible via YAML rules
- **Outputs**: structured JSON + Markdown reports.
- **LLM rationales (optional)**.
- **REST API** with Swagger UI (`/docs`).
- **Batch runner** (`main.py`) for testing against local `data/*.pdf`.
- **Frontend UI** for managing rule packs and uploading PDFs.

---

## 📂 Project Structure

```
backend/
  app.py               # FastAPI app entrypoint
  db.py                # Database engine/session
  bootstrap_db.py      # Seeder: load YAML packs into DB
  models_rulepack.py   # SQLAlchemy model (rule_packs table)
  rulepack_dtos.py     # Pydantic schemas for rule packs
  rulepack_loader.py   # Service to load packs for runtime
  yaml_importer.py     # Import YAML → DB rows
  evaluator.py         # Core evaluator + Markdown writers
  ingest.py            # PDF ingestion utilities
  doc_type.py          # Document type guessing
  telemetry.py         # Simple logging / telemetry hooks
  main.py              # Batch runner (local dev tool)
  schemas.py           # Core Pydantic models

frontend/
  .env                 # Frontend environment variables (VITE_API_BASE_URL)
  package.json         # Frontend dependencies & scripts
  vite.config.ts       # Vite config (React + SWC)
  tsconfig.json        # TypeScript configuration
  index.html           # Entry HTML
  public/              # Static assets
  src/
    api/               # Axios client + DTOs
    components/        # Navbar, FileRow, ReportCard, RulePackEditor
    pages/             # Dashboard, Upload, Documents, RulePacks
    App.tsx            # Router & layout
    main.tsx           # React entrypoint
    theme.css          # Global theme (navy blue / Volaris styling)
```

---

## 🗄 Database Setup (Postgres)

The backend connects to Postgres using the `DATABASE_URL` environment variable.  
Default (from `db.py` and `bootstrap_db.py`):

```
postgresql+psycopg2://postgres:1219@localhost:5432/contractextract
```

### Create Database
```bash
# Log into Postgres (adjust username/password if needed)
psql -U postgres

# Inside psql:
CREATE DATABASE contractextract;
```

### Rule Pack Table Schema

**Table: `rule_packs`**

| Column                   | Type        | Description                                   |
|---------------------------|-------------|-----------------------------------------------|
| `id`                     | text        | Stable identifier (e.g., `strategic_alliance`) |
| `version`                | int         | Version number (composite PK with `id`)       |
| `status`                 | enum        | `draft` \| `active` \| `deprecated`         |
| `schema_version`         | text        | Rulepack schema version (default: `"1.0"`)    |
| `doc_type_names`         | jsonb       | List of names/aliases for type detection      |
| `ruleset_json`           | jsonb       | Parsed `RuleSet` (jurisdiction, liability, etc.) |
| `rules_json`             | jsonb       | Extended rules (optional, extensible)         |
| `llm_prompt`             | text        | Seed prompt for LLM rationale (optional)      |
| `llm_examples_json`      | jsonb       | Examples for LLM extraction (optional)        |
| `extensions_json`        | jsonb       | Optional extensions                           |
| `extensions_schema_json` | jsonb       | Schema for extensions                         |
| `raw_yaml`               | text        | Original YAML (round-trippable)               |
| `notes`                  | text        | Human notes                                   |
| `created_by`             | text        | Author / importer                             |
| `created_at`             | timestamptz | Auto-set                                      |
| `updated_at`             | timestamptz | Auto-set on update                            |

---

## ⚙️ API Overview

Once the server is running, docs are at <http://localhost:8000/docs>.

### Rule Pack Endpoints
- `GET /rule-packs/all` → list all packs
- `GET /rule-packs/{id}` → list versions
- `GET /rule-packs/{id}/{version}` → details
- `GET /rule-packs/{id}/{version}/yaml` → download original YAML
- `POST /rule-packs/import-yaml` → import YAML as draft (paste text)
- `POST /rule-packs/upload-yaml` → import YAML as draft (file)
- `POST /rule-packs/{id}/{version}:publish` → publish a draft
- `POST /rule-packs/{id}/{version}:deprecate` → deprecate
- `PUT /rule-packs/{id}/{version}` → edit draft (JSON patch or YAML)
- `DELETE /rule-packs/{id}/{version}` → delete draft (`?force=true` to override)

### Evaluation Endpoints
- `POST /preview-run` → Upload a PDF → detect type → evaluate → return Markdown report.

---

## 🚀 Getting Started

### Backend
1. Ensure Postgres is running and `DATABASE_URL` is set.
2. Install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
3. Seed rule packs:
   ```bash
   python bootstrap_db.py
   ```
4. Run API:
   ```bash
   uvicorn app:app --reload --port 8000
   ```

### Frontend
1. Navigate into the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the dev server:
   ```bash
   npm run dev
   ```
   App runs at <http://localhost:5173>

---

## 📌 Roadmap

- [ ] Refactor backend into clean layered structure  
- [ ] Extend React frontend with filtering and job tracking  
- [ ] Add Alembic migrations  
- [ ] Add “compare versions” view for packs  
- [ ] Extend evaluator with plugin system (`eval_<type>.py`)  
- [ ] LLM prompt generation for new packs  
- [ ] Fine-tune AdaptLLM-Legal on MAUD dataset  
- [ ] RAG support for policy references  
- [ ] Chatbot rulepack assistant  

---

## 👥 Team

- **Developer**: Noah Collins  
- **Project Manager**: Trey Drake
