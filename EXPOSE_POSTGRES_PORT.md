# Expose LibreChat PostgreSQL Port

If you want to access LibreChat's PostgreSQL from your local machine (useful for debugging, pgAdmin, etc.), add port mapping.

## Steps:

### 1. Find docker-compose.override.yml (or create it)

In your LibreChat directory, check if `docker-compose.override.yml` exists:

```powershell
cd C:\Users\noahc\LibreChat
ls docker-compose.override.yml
```

### 2. Add Port Mapping

If the file exists, edit it. If not, create it with this content:

```yaml
# docker-compose.override.yml
version: '3.4'

services:
  contractextract-db:
    ports:
      - "5433:5432"  # Expose on port 5433 to avoid conflict with local PostgreSQL
```

**Note:** Using port `5433` to avoid conflicts if you have PostgreSQL running locally on `5432`.

### 3. Restart LibreChat

```powershell
docker-compose down
docker-compose up -d
```

### 4. Verify Port is Exposed

```powershell
docker ps | findstr contractextract-db
```

Should show: `0.0.0.0:5433->5432/tcp`

### 5. Seed from Local Machine

Now you can run the seed script locally:

```powershell
cd C:\Users\noahc\PycharmProjects\langextract
.\.venv\Scripts\Activate.ps1

# Set DATABASE_URL to exposed port
$env:DATABASE_URL="postgresql+psycopg2://postgres:contractextract_pass@localhost:5433/contractextract"

# Run seed
python seed_database.py
```

### 6. Test

```powershell
# Restart LibreChat to pick up changes
cd C:\Users\noahc\LibreChat
docker-compose restart

# Test in LibreChat
# "call get_system_info"
# Should show 7 active packs
```

## Connect with pgAdmin (Optional)

Once port is exposed, you can connect with pgAdmin:

- **Host:** localhost
- **Port:** 5433
- **Database:** contractextract
- **User:** postgres
- **Password:** contractextract_pass