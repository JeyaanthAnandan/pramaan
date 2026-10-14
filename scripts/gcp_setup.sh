#!/usr/bin/env bash
# One-time Google Cloud setup for Pramaan (brief 0.1, steps 4-7). Idempotent.
# Prerequisites (human): billing linked, budget alert set, `gcloud auth login` +
# `gcloud auth application-default login` as the project owner.
set -euo pipefail
PROJECT="${PROJECT:-copilot-manufacturing}"
REGION="${REGION:-asia-southeast1}"
BUCKET="${BUCKET:-copilot-manufacturing-pramaan}"
SA_NAME="pramaan-run"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT" >/dev/null
echo "== billing"
gcloud billing projects describe "$PROJECT" --format="value(billingEnabled,billingAccountName)"
[ "$(gcloud billing projects describe "$PROJECT" --format='value(billingEnabled)')" = "True" ] || { echo "Billing is not linked: link a billing account first."; exit 1; }

echo "== APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com \
  firestore.googleapis.com storage.googleapis.com secretmanager.googleapis.com logging.googleapis.com cloudtrace.googleapis.com iam.googleapis.com \
  cloudkms.googleapis.com

echo "== Firestore (Native, $REGION)"
gcloud firestore databases describe --database="(default)" >/dev/null 2>&1 || gcloud firestore databases create --location="$REGION" --type=firestore-native

echo "== Bucket gs://$BUCKET"
gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1 || gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access --public-access-prevention

echo "== Service account $SA"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || gcloud iam service-accounts create "$SA_NAME" --display-name="Pramaan Cloud Run"
for ROLE in roles/aiplatform.user roles/datastore.user roles/logging.logWriter roles/cloudtrace.agent; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role="$ROLE" --condition=None >/dev/null
done
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$SA" --role=roles/storage.objectAdmin >/dev/null

echo "== Report signing key (Cloud KMS, EC P-256): signs every report's receipt; the private key never leaves KMS"
KEYRING="${KEYRING:-pramaan}"
KEY="${KEY:-report-signing}"
gcloud kms keyrings describe "$KEYRING" --location="$REGION" >/dev/null 2>&1 || gcloud kms keyrings create "$KEYRING" --location="$REGION"
gcloud kms keys describe "$KEY" --keyring="$KEYRING" --location="$REGION" >/dev/null 2>&1 || \
  gcloud kms keys create "$KEY" --keyring="$KEYRING" --location="$REGION" --purpose=asymmetric-signing \
    --default-algorithm=ec-sign-p256-sha256 --protection-level=software
for ROLE in roles/cloudkms.signer roles/cloudkms.publicKeyViewer; do  # sign and read the public key: nothing else
  gcloud kms keys add-iam-policy-binding "$KEY" --keyring="$KEYRING" --location="$REGION" \
    --member="serviceAccount:$SA" --role="$ROLE" >/dev/null
done
echo "SIGNING_KEY=projects/$PROJECT/locations/$REGION/keyRings/$KEYRING/cryptoKeys/$KEY/cryptoKeyVersions/1"

echo "== Gemini model availability (location global)"
for M in gemini-3.8-flash gemini-3.5-flash-lite; do
  curl -s -o /dev/null -w "$M: HTTP %{http_code}\n" -X POST \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "Content-Type: application/json" \
    "https://aiplatform.googleapis.com/v1/projects/$PROJECT/locations/global/publishers/google/models/$M:generateContent" \
    -d '{"contents":[{"role":"user","parts":[{"text":"ping"}]}]}'
done

echo "== Summary"
gcloud services list --enabled --format="value(config.name)" | grep -E "run|aiplatform|firestore|storage|secretmanager|logging|cloudtrace|cloudbuild|artifactregistry|iam" | sort
gcloud projects get-iam-policy "$PROJECT" --flatten="bindings[].members" --filter="bindings.members:$SA" --format="value(bindings.role)"
