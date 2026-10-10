#!/usr/bin/env bash
# Deploy Pramaan to Cloud Run (one service: API + SPA). Runs the golden tests first.
set -euo pipefail
PROJECT="${PROJECT:-copilot-manufacturing}"
REGION="${REGION:-asia-southeast1}"
BUCKET="${BUCKET:-copilot-manufacturing-pramaan}"
SA="pramaan-run@${PROJECT}.iam.gserviceaccount.com"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== pre-deploy gate: golden EC tests + refdata manifest"
(cd "$ROOT/backend" && GEMINI_VERTEX_READY=0 .venv/bin/python -m pytest -q tests/test_golden_ec.py tests/test_refdata_manifest.py)

SHA="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo dev)"
gcloud run deploy pramaan --source "$ROOT" --project "$PROJECT" --region "$REGION" \
  --service-account "$SA" --allow-unauthenticated \
  --cpu 2 --memory 2Gi --min-instances 1 --max-instances 3 --concurrency 60 --cpu-boost --session-affinity --timeout 900 \
  --set-env-vars "STORE_BACKEND=firestore,PRAMAAN_BUCKET=$BUCKET,GOOGLE_CLOUD_PROJECT=$PROJECT,GEMINI_MODE=vertex,GEMINI_LOCATION=global,GIT_SHA=$SHA,MAX_RUNS_PER_HOUR=20"

URL="$(gcloud run services describe pramaan --project "$PROJECT" --region "$REGION" --format='value(status.url)')"
echo "== smoke test $URL"
curl -fsS "$URL/healthz" | head -c 400; echo
curl -fsS -X POST "$URL/api/demo/load" -H 'content-type: application/json' -d '{}' | head -c 300; echo
TOKEN="$(curl -fsS -X POST "$URL/api/projects/demo-shivalik/share" | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')"
curl -fsS "$URL/api/share/$TOKEN" | head -c 200; echo
curl -fsS "$URL/api/golden" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("golden all_pass:", d["all_pass"])'
echo "Live: $URL   Buyer link: $URL/share/$TOKEN"
