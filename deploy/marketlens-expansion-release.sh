#!/usr/bin/env bash
# Deploy the tested expansion from an authenticated Cloud Shell.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: bash deploy/marketlens-expansion-release.sh --code-only [--refresh-analytics]" >&2
  echo "   or: bash deploy/marketlens-expansion-release.sh /path/to/listings.json [/path/to/photos.py]" >&2
  exit 2
fi

data=""
photos=""
refresh=false
if [[ "$1" == --code-only ]]; then
  if [[ $# -eq 2 ]]; then
    [[ "$2" == --refresh-analytics ]] || exit 2
    refresh=true
  fi
else
  refresh=true
  data=$(realpath "$1")
  test -s "$data"
  if [[ $# -eq 2 ]]; then
    photos=$(realpath "$2")
    test -s "$photos"
  fi
fi
cd "$(git rev-parse --show-toplevel)"
git diff --quiet HEAD

project=hackos20
region=us-central1
site=https://hackos20.web.app
sha=$(git rev-parse HEAD)
image="$region-docker.pkg.dev/$project/marketlens/api:$sha"
cloud=(gcloud --project="$project" --quiet)

api=$("${cloud[@]}" run services describe marketlens-api --region="$region" \
  --format='value(status.url)')
[[ "$api" == https://*.run.app ]]
config=$(curl -fsS --max-time 30 "$site/__/firebase/init.json")
[[ "$(jq -er '.projectId' <<<"$config")" == "$project" ]]

export MARKETLENS_FIREBASE_PROJECT_ID="$project"
export VITE_MARKETLENS_FIREBASE_PROJECT_ID="$project"
export VITE_MARKETLENS_FIREBASE_API_KEY="$(jq -er '.apiKey' <<<"$config")"
export VITE_MARKETLENS_FIREBASE_AUTH_DOMAIN="$(jq -er '.authDomain' <<<"$config")"
export VITE_MARKETLENS_FIREBASE_APP_ID="$(jq -er '.appId' <<<"$config")"
export VITE_MARKETLENS_API_BASE_URL="$api"

# Build all release inputs before changing the live API.
(cd frontend && npm ci && npm run build:marketlens:hosting)
if [[ "$refresh" == true ]]; then
  venv_dir=$(mktemp -d)
  trap 'rm -rf "$venv_dir"' EXIT
  python3 -m venv "$venv_dir"
  "$venv_dir/bin/pip" -q install uv==0.12.23
  (cd backend && "$venv_dir/bin/uv" sync --frozen --python 3.12)
fi

"${cloud[@]}" builds submit --config=deploy/marketlens-cloudbuild.yaml \
  --substitutions="_IMAGE=$image"
"${cloud[@]}" run deploy marketlens-api --region="$region" --image="$image"
curl -fsS --max-time 30 "$api/api/v1/health" | jq -e '.status == "ok"' >/dev/null

radar_status=$(curl -sS --max-time 30 -o /dev/null -w '%{http_code}' "$api/api/v1/market/radar")
if [[ "$radar_status" != 401 ]]; then
  echo "The deployed radar route returned HTTP $radar_status; expected 401 before login." >&2
  exit 1
fi

if [[ "$refresh" == true ]]; then
  export MARKETLENS_FIREBASE_ENABLED=true
  (
    cd backend
    .venv/bin/python - "$data" <<'PY'
import json
import subprocess
import sys
from unittest.mock import patch

from google.oauth2.credentials import Credentials

from app.marketlens.import_listings import main as import_listings
from app.marketlens.refresh_analytics import refresh_analytics
from app.marketlens.runtime import marketlens_runtime
from app.marketlens.settings import MarketLensSettings
from app.marketlens.store import MarketStore

path = sys.argv[1]
token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
credentials = Credentials(token=token, quota_project_id="hackos20")

with patch("google.auth.default", return_value=(credentials, "hackos20")):
    if path:
        sys.argv = ["import_listings", path]
        import_listings()
    runtime = marketlens_runtime(MarketLensSettings())
    try:
        summary = refresh_analytics(MarketStore(runtime.db()))
    finally:
        runtime.close()
    if (
        summary["scanLimited"]
        or not summary["scannedCount"]
        or summary["savedResults"] != summary["scannedCount"]
    ):
        raise SystemExit("Analytics refresh did not publish every catalog result; stop before Hosting.")
    print(json.dumps(summary))
PY
    if [[ -n "$photos" ]]; then
      .venv/bin/python "$photos" "$project"
    fi
  )
fi

npx --yes firebase-tools@15.34.0 deploy \
  --project "$project" --config firebase.marketlens.json --only hosting --non-interactive
for attempt in {1..6}; do
  if curl -fsS --max-time 15 "$site/release.json" \
     | jq -e --arg sha "$sha" '.commit == $sha' >/dev/null; then
    printf 'SITE=%s\nCOMMIT=%s\n' "$site" "$sha"
    exit 0
  fi
  sleep 5
done
echo "Hosting deployed, but the public release marker has not matched yet." >&2
exit 1
