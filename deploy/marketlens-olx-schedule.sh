#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || "$1" != --authorized ]]; then
  echo "Usage: bash deploy/marketlens-olx-schedule.sh --authorized" >&2
  echo "Confirm OLX permits this recurring collection before running." >&2
  exit 2
fi

project=hackos20
region=us-central1
job=marketlens-olx
schedule=marketlens-olx-daily
runtime_account="marketlens-api@$project.iam.gserviceaccount.com"
scheduler_account="marketlens-scheduler@$project.iam.gserviceaccount.com"
cloud=(gcloud --project="$project" --quiet)

# Use the immutable image of the revision the operator has already released.
revision=$("${cloud[@]}" run services describe marketlens-api --region="$region" \
  --format='value(status.latestReadyRevisionName)')
image=$("${cloud[@]}" run revisions describe "$revision" --region="$region" \
  --format='value(status.imageDigest)')
if [[ "$image" != "$region-docker.pkg.dev/$project/marketlens/api@sha256:"* ]]; then
  echo "Could not resolve the immutable image of the deployed MarketLens API." >&2
  exit 1
fi

"${cloud[@]}" run jobs deploy "$job" --region="$region" --image="$image" \
  --service-account="$runtime_account" --tasks=1 --parallelism=1 \
  --max-retries=0 --task-timeout=180s \
  --command=/app/.venv/bin/python \
  --args='-m,app.marketlens.update_olx,--authorized,--query=iphone 15,--pages=2,--limit=60' \
  --set-env-vars="MARKETLENS_FIREBASE_ENABLED=true,MARKETLENS_FIREBASE_PROJECT_ID=$project"

if ! "${cloud[@]}" run jobs execute "$job" --region="$region" --wait; then
  echo "The manual import failed. No schedule changes were applied." >&2
  "${cloud[@]}" logging read \
    "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$job\" AND resource.labels.location=\"$region\"" \
    --limit=12 --freshness=15m --format='value(textPayload)' >&2 || true
  exit 1
fi

"${cloud[@]}" services enable cloudscheduler.googleapis.com
if ! "${cloud[@]}" iam service-accounts describe "$scheduler_account" >/dev/null 2>&1; then
  "${cloud[@]}" iam service-accounts create marketlens-scheduler
fi
"${cloud[@]}" run jobs add-iam-policy-binding "$job" --region="$region" \
  --member="serviceAccount:$scheduler_account" --role=roles/run.invoker >/dev/null

action=create
if "${cloud[@]}" scheduler jobs describe "$schedule" --location="$region" >/dev/null 2>&1; then
  action=update
fi
"${cloud[@]}" scheduler jobs "$action" http "$schedule" --location="$region" \
  --schedule='0 9 * * *' --time-zone=Asia/Almaty --http-method=POST \
  --uri="https://run.googleapis.com/v2/projects/$project/locations/$region/jobs/$job:run" \
  --oauth-service-account-email="$scheduler_account" \
  --oauth-token-scope=https://www.googleapis.com/auth/cloud-platform \
  --attempt-deadline=30s --max-retry-attempts=0

"${cloud[@]}" scheduler jobs describe "$schedule" --location="$region" \
  --format='table(name,state,schedule,timeZone)'
