# Seed LibreChat's PostgreSQL database from within Docker network
# This script copies the seed script and rule packs into a container and runs it

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Seeding LibreChat PostgreSQL Database" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Copy files into the LibreChat container
Write-Host "`n1. Copying files to LibreChat container..." -ForegroundColor Yellow

docker cp seed_database.py LibreChat:/tmp/
docker cp infrastructure.py LibreChat:/tmp/
docker cp rulepack_manager.py LibreChat:/tmp/
docker cp contract_analyzer.py LibreChat:/tmp/
docker cp document_analysis.py LibreChat:/tmp/
docker cp rules_packs LibreChat:/tmp/

Write-Host "   Files copied successfully" -ForegroundColor Green

# Step 2: Set environment variable for correct database
Write-Host "`n2. Running seed script with LibreChat database..." -ForegroundColor Yellow

$dbUrl = "postgresql+psycopg2://postgres:contractextract_pass@librechat-contractextract-db-1:5432/contractextract"

docker exec -e DATABASE_URL=$dbUrl LibreChat bash -c "cd /tmp && python3 seed_database.py"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Seeding Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Restart LibreChat: docker-compose restart" -ForegroundColor White
Write-Host "  2. Test: call get_system_info in LibreChat" -ForegroundColor White
Write-Host "  3. Expected: 7 active rule packs" -ForegroundColor White