# OptionsIQ — Cloud Run Deployment Guide

## What you'll get

A private, password-protected URL like `https://optionsiq-XXXXX.a.run.app`
that you can share with your friends. They need the password to access it.

## Cost reality check

This deployment fits inside Google Cloud Run's **always-free tier**: 2 million
requests/month and 360,000 GB-seconds memory free. For a personal app used by
you and a few friends you should pay **₹0**.

But you should know two things:

1. **Cloud Run scales to zero when idle.** After ~15 minutes of no traffic the
   container shuts down. Next request triggers a 5–30 second cold start. The
   live WebSocket tick feed dies during idle. The Quick Scalp Engine and live
   1-minute candles will mostly show "waiting for ticks" on the deployed
   version. The AI Decision Engine, GIFT Nifty, FII/DII, sentiment, option
   chain — all work fine.

2. **The Paytm WebSocket may not connect from a US-region container** even
   when warm. If it doesn't, the app degrades to REST polling automatically.

## Prerequisites (one time)

1. A Google account.
2. Install the gcloud CLI: <https://cloud.google.com/sdk/docs/install>
3. Create a Google Cloud project:
   ```bash
   gcloud auth login
   gcloud projects create optionsiq-prod --name="OptionsIQ"
   gcloud config set project optionsiq-prod
   ```
4. Enable billing on the project (required even for free-tier usage). Go to
   <https://console.cloud.google.com/billing> and link a card. You won't be
   charged unless you exceed the free tier.
5. Enable the Cloud Run + Cloud Build APIs:
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com
   ```

## Deploy

From your project folder:

```bash
gcloud run deploy optionsiq \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 3600 \
    --set-env-vars OPTIONSIQ_APP_PASSWORD=YOUR_REAL_PASSWORD_HERE
```

Replace `YOUR_REAL_PASSWORD_HERE` with the actual 8+ character password you
want to share. Cloud Build will build the Docker image, push it, and deploy.
Takes about 5 minutes the first time, ~2 minutes for re-deploys.

When it finishes, you'll see:
```
Service URL: https://optionsiq-XXXXXXXXXX-uc.a.run.app
```

That's your URL. Share it with friends along with the password.

## Update the password later

```bash
gcloud run services update optionsiq \
    --region us-central1 \
    --update-env-vars OPTIONSIQ_APP_PASSWORD=NEW_PASSWORD
```

## Re-deploy after code changes

Same `gcloud run deploy` command as above — it picks up your latest code.
You don't need to repeat the env vars unless you want to change them.

## Tail logs (for debugging)

```bash
gcloud run services logs read optionsiq --region us-central1 --limit 100
```

Or view in the browser at <https://console.cloud.google.com/run> → click on
"optionsiq" → "Logs" tab.

## Tear it down

If you want to stop everything:

```bash
gcloud run services delete optionsiq --region us-central1
```

This is reversible — you can re-deploy with the same command later.

## Things to verify after first deploy

- [ ] Open the URL — see the password prompt
- [ ] Wrong password → red error message
- [ ] Correct password → app loads, you see the OptionsIQ sidebar
- [ ] Enter your Paytm credentials in the sidebar → option chain loads
- [ ] Enter your Anthropic API key → AI Decision Engine works
- [ ] GIFT Nifty card shows real value matching Groww (not Yahoo proxy)

## Security notes

- The password is stored as a Cloud Run environment variable, NOT in the
  GitHub repo. Never put the real password in `auth_gate.py`.
- Anyone with the URL + password can use your Anthropic API key. Set a
  budget alert in the Anthropic console: <https://console.anthropic.com/>
- Anyone with the URL + password can read your Paytm option chain data
  through your authenticated session. Don't share the URL with strangers.
- The password gate is single-shared-password. It is NOT a substitute for
  per-user auth. Do not use this if you ever expand beyond friends.
