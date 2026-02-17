# Deploy content-service to Cloud Run

## 1. Build the image

**Option A: Local Docker (recommended if `gcloud builds submit` fails)**

```bash
./build-and-push.sh
# Or: docker build -t gcr.io/biso-event/content-service .
#     gcloud auth configure-docker gcr.io --quiet
#     docker push gcr.io/biso-event/content-service
```

**Option B: Cloud Build**

```bash
gcloud builds submit --tag gcr.io/biso-event/content-service .
```

## 2. Store API key in Secret Manager (recommended)

**Important:** Do not put your OpenAI API key in the deploy command. Rotate any key that was exposed.

```bash
# Create the secret (paste your key when prompted)
echo -n "sk-your-openai-key" | gcloud secrets create openai-api-key --data-file=-

# Or update if it exists
echo -n "sk-your-openai-key" | gcloud secrets versions add openai-api-key --data-file=-
```

## 3. Deploy to Cloud Run

**Using Secret Manager (recommended):**
```bash
gcloud run deploy content-service \
  --image gcr.io/biso-event/content-service \
  --platform managed \
  --region us-central1 \
  --set-secrets=OPENAI_API_KEY=openai-api-key:latest \
  --allow-unauthenticated \
  --memory 512Mi \
  --min-instances 0
```

**Using env var (only for quick testing, rotate key afterward):**
```bash
gcloud run deploy content-service \
  --image gcr.io/biso-event/content-service \
  --platform managed \
  --region us-central1 \
  --set-env-vars OPENAI_API_KEY=your-key-here \
  --allow-unauthenticated \
  --memory 512Mi
```

## 4. Get the service URL

```bash
gcloud run services describe content-service --region us-central1 --format 'value(status.url)'
```

Use this URL as `CONTENT_SERVICE_URL` in your biso-event mobile app.

## Required APIs

Enable these if not already:
```bash
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```
