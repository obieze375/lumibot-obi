# Cloud Scheduler → Cloud Run Jobs (Europe/London)
#
# Screen window: 08:00–13:00 London every 15 minutes
#   0,15,30,45 8-12 * * 1-5
#
# Manage window: ~14:30–21:00 London (NYSE cash hours) every 2 minutes
#   */2 14-20 * * 1-5
#
# Example gcloud commands (placeholders only):

# gcloud run jobs deploy skope-screen \
#   --image=REGION-docker.pkg.dev/PROJECT/REPO/skope-io:latest \
#   --region=us-central1 \
#   --set-secrets=DATABASE_URL=DATABASE_URL:latest,FINNHUB_API_KEY=FINNHUB_API_KEY:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,ALPACA_API_KEY=ALPACA_API_KEY:latest,ALPACA_API_SECRET=ALPACA_API_SECRET:latest,SKOPE_API_TOKEN=SKOPE_API_TOKEN:latest \
#   --command=python,--module-not-used \
#   --args=-m,strategy.runner,--mode,screen \
#   --memory=512Mi --cpu=1 --task-timeout=900 --max-retries=1

# gcloud scheduler jobs create http skope-screen-cron \
#   --location=us-central1 \
#   --schedule="0,15,30,45 8-12 * * 1-5" \
#   --time-zone="Europe/London" \
#   --uri="https://REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT/jobs/skope-screen:run" \
#   --http-method=POST \
#   --oauth-service-account-email=SCHEDULER_SA@PROJECT.iam.gserviceaccount.com

# gcloud scheduler jobs create http skope-manage-cron \
#   --location=us-central1 \
#   --schedule="*/2 14-20 * * 1-5" \
#   --time-zone="Europe/London" \
#   --uri="https://REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT/jobs/skope-manage:run" \
#   --http-method=POST \
#   --oauth-service-account-email=SCHEDULER_SA@PROJECT.iam.gserviceaccount.com

# API service (scale-to-zero) for Netlify dashboard 1-click trades:
# gcloud run deploy skope-api \
#   --image=REGION-docker.pkg.dev/PROJECT/REPO/skope-io:latest \
#   --region=us-central1 \
#   --allow-unauthenticated=false \
#   --min-instances=0 --max-instances=2 \
#   --memory=512Mi --cpu=1 \
#   --set-secrets=...
