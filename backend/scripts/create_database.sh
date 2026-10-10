#!/usr/bin/env bash
# Creates the PostgreSQL role + databases described by DATABASE_URL in backend/.env.
# Run once:  bash backend/scripts/create_database.sh   (asks for your sudo password)
set -euo pipefail
cd "$(dirname "$0")/.."
URL=$(grep -E '^DATABASE_URL=' .env | cut -d= -f2-)
read -r USER PASS DB < <(python3 - "$URL" <<'PY'
import sys
from urllib.parse import urlsplit, unquote
u = urlsplit(sys.argv[1].replace("+asyncpg", ""))
print(unquote(u.username), unquote(u.password), u.path.lstrip("/"))
PY
)
sudo -u postgres psql -v ON_ERROR_STOP=1 \
  -v user="$USER" -v pass="$PASS" -v db="$DB" -v testdb="${DB}_test" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'user', :'pass')
  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'user') \gexec
SELECT format('ALTER ROLE %I PASSWORD %L', :'user', :'pass') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'user')
  WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'testdb', :'user')
  WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'testdb') \gexec
SQL
echo "Created/updated role '$USER' and databases '$DB', '${DB}_test'."
