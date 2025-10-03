# ContractExtract PostgreSQL Database Setup

## ✅ Database Configuration

The ContractExtract MCP server requires its own PostgreSQL database to store rule packs and analysis configurations.

### Database Service

**Service Name:** `contractextract-db`
**Image:** `postgres:15-alpine`
**Database Name:** `contractextract`
**User:** `postgres`
**Password:** `contractextract_pass`
**Internal Port:** `5432`
**Volume:** `contractextract-db-data`

### Connection String

**Used by MCP Server:**
```
postgresql+psycopg2://postgres:contractextract_pass@contractextract-db:5432/contractextract
```

**Configured in:** `librechat.yaml` under `mcpServers.contractextract.env.DATABASE_URL`

---

## 📊 Database Schema

### `rule_packs` Table

Stores versioned YAML-based rule configurations for contract analysis.

**Key Columns:**
- `id` - Primary key
- `name` - Rule pack name (e.g., "ip_assignment", "termination_clauses")
- `version` - Semantic version (e.g., "1.0.0", "2.1.3")
- `status` - "active", "draft", "deprecated"
- `yaml_content` - JSONB field with full rule configuration
- `description` - Human-readable description
- `author` - Creator/owner
- `created_at` - Timestamp
- `updated_at` - Last modification timestamp

---

## 🔧 Database Operations

### Access Database Shell
```bash
docker compose exec contractextract-db psql -U postgres -d contractextract
```

### Common Queries

**List all rule packs:**
```sql
SELECT name, version, status, author, created_at
FROM rule_packs
ORDER BY created_at DESC;
```

**Count rule packs by status:**
```sql
SELECT status, COUNT(*) as count
FROM rule_packs
GROUP BY status;
```

**Get active rule packs:**
```sql
SELECT name, version, description
FROM rule_packs
WHERE status = 'active';
```

**View specific rule pack YAML:**
```sql
SELECT name, version, yaml_content
FROM rule_packs
WHERE name = 'your_rulepack_name'
  AND status = 'active'
LIMIT 1;
```

---

## 🛠️ Management Tasks

### Backup Database
```bash
docker compose exec contractextract-db pg_dump -U postgres contractextract > backup.sql
```

### Restore Database
```bash
docker compose exec -T contractextract-db psql -U postgres -d contractextract < backup.sql
```

### Clear All Data (Destructive!)
```bash
docker compose exec contractextract-db psql -U postgres -d contractextract -c "TRUNCATE TABLE rule_packs CASCADE;"
```

### Drop and Recreate Database
```bash
docker compose down contractextract-db
docker volume rm librechat_contractextract-db-data
docker compose up -d contractextract-db
```

---

## 🚀 How It Works

### 1. Startup Flow
```
1. docker compose up starts contractextract-db service
2. PostgreSQL initializes with empty contractextract database
3. LibreChat (api service) waits for contractextract-db to be healthy
4. MCP server spawns with DATABASE_URL environment variable
5. MCP server connects to PostgreSQL
6. SQLAlchemy creates rule_packs table if not exists
7. Server initializes and registers 15 tools
```

### 2. Rule Pack Lifecycle
```
Draft → Active → Deprecated
  ↓       ↓          ↓
(editing) (in use)  (archived)
```

### 3. MCP Tools Access Database
When agents use MCP tools, they query/modify the PostgreSQL database:
- `list_all_rulepacks` → SELECT * FROM rule_packs
- `list_active_rulepacks` → SELECT * WHERE status='active'
- `create_rulepack_from_yaml` → INSERT INTO rule_packs
- `update_rulepack_yaml` → UPDATE rule_packs
- `publish_rulepack` → UPDATE status='active'
- `deprecate_rulepack` → UPDATE status='deprecated'
- `delete_rulepack` → DELETE FROM rule_packs

---

## 📝 Seeding Initial Data

The MCP server auto-creates the `rule_packs` table on first connection. To seed with initial rule packs:

### Option 1: Via MCP Tools (Recommended)
1. Create agent in LibreChat with contractextract tools
2. Use `create_rulepack_from_yaml` tool
3. Provide YAML rule pack configuration
4. Use `publish_rulepack` to activate

### Option 2: Direct SQL Insert
```sql
INSERT INTO rule_packs (name, version, status, yaml_content, description, author)
VALUES (
  'example_pack',
  '1.0.0',
  'active',
  '{"rules": [...], "metadata": {...}}'::jsonb,
  'Example rule pack for testing',
  'admin'
);
```

### Option 3: Import from Host
If you have a bootstrap script in your langextract project:
```bash
# Copy bootstrap data to container
docker compose cp C:/Users/noahc/PycharmProjects/langextract/bootstrap_data.sql contractextract-db:/tmp/

# Execute in database
docker compose exec contractextract-db psql -U postgres -d contractextract -f /tmp/bootstrap_data.sql
```

---

## ⚠️ Important Notes

### Database Isolation
- **contractextract-db** is separate from **vectordb** (LibreChat RAG)
- **contractextract-db** is separate from **mongodb** (LibreChat main DB)
- Each database serves a different purpose and should not be mixed

### Health Checks
The database must pass health checks before LibreChat starts:
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres -d contractextract"]
  interval: 10s
  timeout: 5s
  retries: 5
```

### Data Persistence
Data is stored in Docker volume: `librechat_contractextract-db-data`
- Survives container restarts
- Persists across `docker compose down` (without `-v` flag)
- Lost if you run `docker compose down -v` or manually remove the volume

### Password Security
**Production deployments should:**
1. Change the default password from `contractextract_pass`
2. Use environment variables for credentials
3. Enable SSL/TLS for database connections
4. Restrict network access to database port

---

## 🐛 Troubleshooting

### MCP Server Can't Connect
**Error:** `connection to server at "contractextract-db" failed`

**Solutions:**
1. Check database is running and healthy:
   ```bash
   docker compose ps contractextract-db
   # Should show: Up (healthy)
   ```

2. Verify network connectivity:
   ```bash
   docker compose exec api ping contractextract-db
   ```

3. Check DATABASE_URL in logs:
   ```bash
   docker compose logs api | grep DATABASE_URL
   ```

### No Rule Packs in Database
**Symptom:** `list_all_rulepacks` returns empty

**Cause:** Fresh database with no seeded data

**Solution:** Create rule packs via MCP tools or import SQL

### Table Does Not Exist
**Error:** `relation "rule_packs" does not exist`

**Cause:** Database initialization failed

**Solution:**
```bash
# Restart api service to retry initialization
docker compose restart api

# Check logs for errors
docker compose logs api | grep -i database
```

### Duplicate Key Errors
**Error:** `duplicate key value violates unique constraint`

**Cause:** Concurrent initialization attempts (non-critical)

**Impact:** None - one initialization succeeds, others fail gracefully

**Prevention:** Not needed - this is handled by the MCP server

---

## 📊 Monitoring

### Check Database Size
```bash
docker compose exec contractextract-db psql -U postgres -d contractextract -c "
SELECT
  pg_size_pretty(pg_database_size('contractextract')) as db_size;
"
```

### Check Table Statistics
```bash
docker compose exec contractextract-db psql -U postgres -d contractextract -c "
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  n_tup_ins AS inserts,
  n_tup_upd AS updates,
  n_tup_del AS deletes
FROM pg_stat_user_tables;
"
```

### View Active Connections
```bash
docker compose exec contractextract-db psql -U postgres -d contractextract -c "
SELECT
  pid,
  usename,
  application_name,
  state,
  query
FROM pg_stat_activity
WHERE datname = 'contractextract';
"
```

---

## ✅ Success Indicators

When everything is working correctly:

1. **Service Status:**
   ```bash
   docker compose ps contractextract-db
   # Shows: Up (healthy)
   ```

2. **Table Exists:**
   ```bash
   docker compose exec contractextract-db psql -U postgres -d contractextract -c "\dt"
   # Shows: rule_packs table
   ```

3. **MCP Server Logs:**
   ```
   Database initialized successfully
   MCP stdio server running - ready for LibreChat connection
   ```

4. **MCP Tools Available:**
   - LibreChat shows 15 contractextract tools
   - Tools can query database without errors

---

## 🔗 Related Documentation

- **MCP Server Code:** `C:\Users\noahc\PycharmProjects\langextract\mcp_server.py`
- **Database Models:** `C:\Users\noahc\PycharmProjects\langextract\rulepack_manager.py`
- **LibreChat Config:** `C:\Users\noahc\LibreChat\librechat.yaml`
- **Docker Compose:** `C:\Users\noahc\LibreChat\docker-compose.override.yml`

---

**Last Updated:** October 2, 2025
**Status:** ✅ Operational
