

# CI/CD setup

export PROJECT_ID="lookahead-ef698"
https://github.com/google-github-actions/auth#setting-up-workload-identity-federation

gcloud iam service-accounts create "lookahead-api-cicd-github" \
  --project "${PROJECT_ID}"


gcloud iam workload-identity-pools create "github-action-pool" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --display-name="Github Action pool"


gcloud iam workload-identity-pools describe "github-action-pool" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --format="value(name)"


gcloud iam workload-identity-pools providers create-oidc "github-action-provider" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github-action-pool" \
  --display-name="Github Action provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"


# TODO(developer): Update this value to your GitHub repository.
export REPO="Lookaheadai/lookahead-api" # e.g. "google/chrome"

gcloud iam service-accounts add-iam-policy-binding "lookahead-api-cicd-github@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL_ID}/attribute.repository/${REPO}"


gcloud iam workload-identity-pools providers describe "github-action-provider" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github-action-pool" \
  --format="value(name)"

projects/969915620660/locations/global/workloadIdentityPools/github-action-pool/providers/github-action-provider


gcloud projects add-iam-policy-binding ${PROJECT_ID} \
      --member="serviceAccount:lookahead-api-cicd-github@${PROJECT_ID}.iam.gserviceaccount.com" \
      --role='roles/run.admin'

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
      --member="serviceAccount:lookahead-api-cicd-github@${PROJECT_ID}.iam.gserviceaccount.com" \
      --role='roles/iam.serviceAccountUser'

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
      --member="serviceAccount:lookahead-api-cicd-github@${PROJECT_ID}.iam.gserviceaccount.com" \
      --role='roles/storage.admin'
      
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
      --member="serviceAccount:lookahead-api-cicd-github@${PROJECT_ID}.iam.gserviceaccount.com" \
      --role='roles/serviceusage.serviceUsageConsumer'