# VIGILA

VIGILA is a full-stack alerting platform that watches the markets and the gift card resale sites so you don't have to. It combines a stock volume/price alert system with a gift card discount scraper, and notifies you by email the moment something crosses your threshold.

**Live app:** [vigila-d6c82.web.app](https://vigila-d6c82.web.app)

## What it does

- **Stock volume alerts** — Track tickers and get notified when trading volume spikes relative to a 5-day rolling average (outlier-resistant, wider lookback window), paired with same-day price change.
- **Gift card discount alerts** — Scrapes CardCash, CardDepot, and GCX for discounted gift cards matching a brand, discount %, and value range you set, and emails you when a new platform crosses your threshold.
- **Position sizing tool** — A quantitative leverage calculator built on geometric Brownian motion (GBM) barrier-breach probability. Given a cash amount, a drawdown tolerance, and a confidence level, it solves for the maximum safe leverage on an index (e.g. SPY) using `scipy.optimize.brentq`, plus a secondary risk-reward-optimal leverage recommendation.
- **Allowlisted signup** — New account creation is gated through a Firebase blocking function against a configurable allowlist.

## Tech stack

**Frontend**

- React 19 + TypeScript, built with Vite
- React Router for client-side routing
- Firebase Auth + Firestore (client SDK)
- Bootstrap for styling

**Backend**

- Python Cloud Functions / Cloud Run services:
  - `gcf/stock_analysis_backend` — GBM-based position sizing endpoint (`scipy`, `numpy`, `yfinance`)
  - `gcf/giftcard_alert_backend` — FastAPI + Playwright scraper orchestrator, containerized and deployed to Cloud Run
  - `gcf/main.py` — scheduled volume alert checker (queries Firestore, pulls data via `yfinance`, emails users)
- Firebase Cloud Functions (TypeScript) — `functions/` handles the pre-signup allowlist check
- Firestore as the primary datastore, with per-user subcollections for `volume_alerts` and `giftcard_alerts`
- Cloud Scheduler (OIDC-authenticated) triggers the periodic alert checks
- Gmail SMTP for email delivery

## Project structure

```
VIGILA/
├── src/                          # React frontend
│   ├── assets/components/        # Pages & UI (Dashboard, StockAlertPage, GiftcardAlertPage, modals, etc.)
│   ├── assets/APIs/               # Firestore/ticker-search client wrappers
│   └── hooks/                     # Custom React hooks
├── functions/                    # Firebase Cloud Functions (TS) — signup allowlist
├── gcf/
│   ├── main.py                    # Scheduled volume alert checker
│   ├── stock_analysis_backend/    # GBM position sizing HTTP function
│   └── giftcard_alert_backend/    # Gift card scraper (FastAPI + Playwright, Cloud Run)
└── firebase.json                 # Hosting & functions config
```

## Getting started

### Frontend

```bash
npm install
npm run dev
```

### Firebase Functions (signup allowlist)

```bash
cd functions
npm install
npm run build
```

### Python backends

Each backend under `gcf/` has its own `requirements.txt`:

```bash
cd gcf/stock_analysis_backend   # or giftcard_alert_backend
pip install -r requirements.txt
```

The gift card backend runs in a Docker container (Playwright + Uvicorn) intended for Cloud Run:

```bash
cd gcf/giftcard_alert_backend
docker build -t giftcard-alert-backend .
```

### Environment variables

The email-sending functions expect:

```
SENDER_EMAIL=your-gmail-address
APP_PASSWORD=your-gmail-app-password
```

## Deployment

- **Frontend:** `firebase deploy --only hosting`
- **Firebase Functions:** `firebase deploy --only functions`
- **Cloud Run (gift card backend):** build and push the Docker image, then deploy to Cloud Run
- **Cloud Function (position sizing / volume alerts):** deploy via `gcloud functions deploy` or the Functions Framework
