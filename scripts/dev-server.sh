#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "$ROOT/.." && pwd)"
LIB="$WORKSPACE/craftify-library"
VENV="$ROOT/.venv"
PORT="${ANVIL_PORT:-3031}"
DB_NAME="${ANVIL_PG_DB:-body_comp_tracker_anvil}"

if [[ ! -x "$VENV/bin/anvil-app-server" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install anvil-app-server pytest
fi
export JAVA_HOME="/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"

ln -sfn "$(basename "$ROOT")" "$WORKSPACE/body_comp_tracker"
ln -sfn craftify-library "$WORKSPACE/craftify_library"

# Reuse craftify-library dependency bootstrap (GitHub tabulator + anvil_extras + routing).
bash "$LIB/scripts/dev-server.sh" &
BOOT=$!
sleep 4
kill "$BOOT" 2>/dev/null || true

if ! pg_isready -q 2>/dev/null; then
  brew services start postgresql@14 2>/dev/null || true
fi
psql -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 \
  || psql -d postgres -c "CREATE DATABASE \"$DB_NAME\";"

cd "$WORKSPACE"
ARGS=(
  --app body_comp_tracker
  --port "$PORT"
  --auto-migrate
  --origin "http://localhost:$PORT"
  --database "jdbc:postgresql://localhost/$DB_NAME?user=$(whoami)"
  --dep-id ST3GINETRT4QJYDC=craftify_library
  --dep-id dep_craftify_lib=craftify_library
  --dep-id dep_r1gjp7ay80bem=craftify_library
  --dep-id TGQCF3WT6FVL2EM2=tabulator
  --dep-id C6ZZPAPN4YYF5NVJ=anvil_extras
  --dep-id dep_d6bjyrizg8vut=tabulator
  --dep-id dep_kfkrna97mklbm=anvil_extras
  --dep-id 3PIDO5P3H4VPEMPL=routing
  --dep-id dep_routing=routing
)
if [[ -n "${ANVIL_GOOGLE_CLIENT_ID:-}" && -n "${ANVIL_GOOGLE_CLIENT_SECRET:-}" ]]; then
  ARGS+=(--google-client-id "$ANVIL_GOOGLE_CLIENT_ID")
  ARGS+=(--google-client-secret "$ANVIL_GOOGLE_CLIENT_SECRET")
fi
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  ARGS+=(--secret "OPENAI_API_KEY=$OPENAI_API_KEY")
fi
exec "$VENV/bin/anvil-app-server" "${ARGS[@]}"
