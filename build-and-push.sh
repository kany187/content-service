#!/bin/bash
# Build locally and push to GCR - bypasses Cloud Build upload issues
set -e

PROJECT_ID="${1:-biso-event}"
IMAGE="gcr.io/${PROJECT_ID}/content-service"

echo "Building Docker image..."
docker build -t "$IMAGE" .

echo "Configuring Docker for GCR..."
gcloud auth configure-docker gcr.io --quiet

echo "Pushing to $IMAGE ..."
docker push "$IMAGE"

echo "Done. Deploy with:"
echo "  gcloud run deploy content-service --image $IMAGE --platform managed --region us-central1 --set-secrets=OPENAI_API_KEY=openai-api-key:latest --allow-unauthenticated --memory 512Mi"
