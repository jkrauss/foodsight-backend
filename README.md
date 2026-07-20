# Foodsight

**ML-powered sales prediction for bakeries** — helps optimize daily stock levels by forecasting product demand for tomorrow, the day after, and the coming week.

Foodsight was built as a SaaS product for artisan bakeries in Germany. It ingests POS sales data and weather forecasts, trains a gradient-boosted model, and presents actionable order suggestions through an intuitive web dashboard.

> **Live demo credentials** — username: `demo` / password: `demo123`

---

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Svelte SPA  │────▶│  FastAPI Backend  │────▶│  ML Pipeline     │
│  (Rollup)    │◀────│  (uvicorn)        │◀────│  (CatBoost)      │
└──────────────┘     └──────────────────┘     └──────────────────┘
       │                     │                         │
       │ JWT auth            │ REST API                │ Scheduled
       │ Static files        │ CORS enabled            │ 2x daily
       ▼                     ▼                         ▼
   Client browser      JSON responses           predictions.csv
```

### Pipeline stages

| Stage | Purpose |
|-------|---------|
| `0_load_*` | Ingest sales history, weather data, date dimensions |
| `1_transform_*` | Clean, normalise, feature-engineer raw data |
| `2_prepare_training_data` | Merge sources, create train/test/predict splits |
| `4_train_model` | Train CatBoost regressor, save production model |
| `6_serve_predictions` | Generate 7-day forecasts per store and product |

### API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/token` | Authenticate, receive JWT |
| `GET` | `/api/forecast/?store={id}` | Sales predictions (authenticated) |
| `GET` | `/api/usersettings/` | User + store configuration |
| `PUT` | `/api/usersettings/` | Update user preferences |
| `POST` | `/api/order` | Export order as Excel/CSV |
| `POST` | `/api/signup` | Register new bakery |
| `POST` | `/api/problem` | Submit feedback with screenshot |

---

## Tech Stack

- **Backend:** Python 3.12, FastAPI, uvicorn, Pandas
- **Frontend:** Svelte 3, SMUI (Material Design), Tailwind CSS, Rollup
- **ML:** CatBoost, scikit-learn, featuretools, tsfresh
- **Auth:** JWT (python-jose), bcrypt password hashing
- **Data:** CSV-based pipeline with TOML configuration
- **Infra:** Docker, Render (staging)

---

## Local Development

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend (in a second terminal)
cd client && npm install && npm run dev
```

The app runs at `http://localhost:8000`. Without login it operates in demo mode with sample data.

---

## Deployment

```bash
docker build -t foodsight .
docker run -p 8000:8000 foodsight
```

Or deploy directly to Render/Railway/Fly.io — the Dockerfile handles everything.

---

## Project Structure

```
foodsight-backend/
├── main.py                 # FastAPI application & routes
├── main_auth.py            # JWT auth & password hashing
├── startup_pipeline.py     # Scheduled pipeline runner
├── requirements.txt
├── Dockerfile
├── client/                 # Svelte frontend
│   ├── src/
│   │   ├── App.svelte
│   │   ├── Foodtable.svelte    # Main prediction table
│   │   ├── Settings.svelte     # User preferences
│   │   ├── Intro.svelte        # Landing page
│   │   └── lib/
│   │       ├── stores.js       # Svelte stores & auth interceptor
│   │       ├── auth/           # Login component
│   │       ├── nav/            # Navigation
│   │       └── components/     # UI components
│   └── public/
│       ├── build/              # Compiled bundle
│       └── *.json              # Demo data files
└── pipeline/
    ├── 0_load_*.py             # Data ingestion
    ├── 1_transform_*.py        # Feature engineering
    ├── 2_prepare_training_data.py
    ├── 4_train_model.py        # Model training
    ├── 6_serve_predictions.py  # Forecast generation
    ├── plugins/                # POS system integrations
    │   ├── oj/                 # Orange juice dataset
    │   └── ready2order/        # ready2order POS API
    └── data/
        └── customer.toml       # Store & user configuration
```

---

## Key Design Decisions

- **TOML for configuration** — human-readable, supports nested tables for multi-store setups, easy to edit without a database
- **Plugin architecture for POS systems** — new cash-register systems can be integrated by adding a plugin module
- **JWT with configurable expiry** — balances security with UX for bakery staff who share terminals
- **CatBoost for ML** — handles categorical features natively (product names, weekdays, holidays) without one-hot encoding
- **Pipeline as scheduled scripts** — each stage is independently runnable for debugging, paired with Jupyter notebooks for exploration

---

## License

MIT

---

*Built by [Jonas Krauss](https://jonaskrauss.de) · [LinkedIn](https://www.linkedin.com/in/kraussjonas/)*
