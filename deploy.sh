#!/bin/bash
name=lookahead-cloud-run-api
project=lookahead-ef698
region=us-west1
repo=gcr.io/$project/$name

# gcloud
gcloud builds submit --project $project --tag $repo
gcloud run deploy --project $project $name --cpu=1 --max-instances=5 --concurrency=20 --memory=1Gi --port=8080 --timeout=60 --image=$repo --region=$region --allow-unauthenticated --clear-env-vars --clear-labels --clear-secrets --no-use-http2
