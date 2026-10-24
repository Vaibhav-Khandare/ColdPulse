# ColdPulse

**AI-Powered Cold Chain Monitoring and Predictive Temperature Excursion Early Warning System**

---

## Overview

ColdPulse is a Django-based web application that monitors cold-chain temperature conditions in real time and provides **predictive early warnings** before a temperature excursion occurs.

The system consists of two cooperating parts:

1. **A Django backend** that ingests telemetry, stores readings in a database, and broadcasts them to connected web clients via WebSocket.
2. **A standalone Tkinter simulator** that runs a physics-based "digital twin" of a cold chamber, uses a trained LightGBM model to predict future temperatures, and pushes readings + predictions to the Django backend over HTTP.

Together, they deliver an end-to-end pipeline: **Simulator → Django API → SQLite → WebSocket → Live Web Dashboard**.

> ⚠️ This is an academic software development project. Predictions and alerts must be validated before any real-world cold-chain safety decisions are made.

---

## Architecture
┌──────────────────────────────────────────────┐
│ Tkinter Simulator │
│ ├─ Physics engine (thermostat, heat leak, │
│ │ door ingress, defrost, warm load) │
│ ├─ LightGBM model (2v.joblib) │
│ │ → predicts temperature at t + 30 min │
│ ├─ 3D digital-twin visualization │
│ └─ HTTP POST every 1 second │
└───────────────────┬──────────────────────────┘
│ HTTP POST (JSON)
▼
┌──────────────────────────────────────────────┐
│ Django + DRF + Channels │
│ ├─ POST /monitoring/api/readings/ │
│ │ → validates & saves to SQLite │
│ │ → broadcasts to WebSocket group │
│ └─ WS /ws/dashboard/ │
│ → pushes JSON to every connected │
│ browser client │
└───────────────────┬──────────────────────────┘
│ WebSocket
▼
┌──────────────────────────────────────────────┐
│ Browser Dashboard │
│ GET /monitoring/dashboard/ │
│ Live cards: temperature, prediction, │
│ risk, power, door, compressor │
└──────────────────────────────────────────────┘

text

---

## Technology Stack

| Layer        | Technology                                         |
|--------------|----------------------------------------------------|
| Backend      | Python 3.13, Django 6.x, **Daphne** (ASGI)         |
| API          | Django REST Framework                              |
| Realtime     | Django Channels (WebSocket), `InMemoryChannelLayer`|
| Database     | SQLite (local development)                         |
| Frontend     | Django Templates, vanilla JavaScript, inline CSS   |
| Simulator    | Tkinter, NumPy, Pandas, Matplotlib, LightGBM, scikit-learn, requests |
| ML model     | LightGBM Regressor (predicts temperature at +30 min) |

---

## Project Structure

```text
ColdPulse/
├── config/
│   ├── settings.py            # daphne first, DRF + Channels configured
│   ├── urls.py                # admin, monitoring, prediction
│   └── asgi.py                # WebSocket routing (ProtocolTypeRouter)
│
├── monitoring/
│   ├── migrations/
│   ├── templates/
│   │   └── monitoring/
│   │       └── dashboard.html # live WebSocket dashboard
│   ├── models.py              # TemperatureReading
│   ├── serializers.py         # TemperatureReadingSerializer
│   ├── consumers.py           # DashboardConsumer (WebSocket)
│   ├── views.py               # CreateView + dashboard_view
│   └── urls.py                # /api/readings/, /dashboard/
│
├── prediction/                # placeholder — model runs in simulator
│
├── simulator/
│   ├── SIMULATOR.py           # physics + ML + Tkinter UI
│   ├── 2v.joblib              # trained LightGBM model (may be large)
│   └── README.md              # how to obtain the .joblib
│
├── templates/
├── static/
├── datasets/
├── manage.py
├── requirements.txt
├── .gitignore
└── README.md
Prerequisites
Python 3.10+ (tested on 3.13)

Git

A GitHub account

Optional: a trained LightGBM .joblib model (see Simulator section)

Setup
1. Clone the repository
bash
git clone https://github.com/Vaibhav-Khandare/ColdPulse.git
cd ColdPulse
2. Create and activate a virtual environment
Windows (PowerShell):

powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
macOS / Linux:

bash
python3 -m venv venv
source venv/bin/activate
3. Install dependencies
bash
python -m pip install --upgrade pip
pip install -r requirements.txt
If requirements.txt is out of date, install the runtime dependencies explicitly:

bash
pip install django daphne channels channels_redis djangorestframework \
            numpy pandas joblib matplotlib lightgbm scikit-learn requests
4. Apply database migrations
bash
python manage.py migrate
5. Verify the project
bash
python manage.py check
Expected: System check identified no issues (0 silenced).

Running the Application
The demo requires two terminals running simultaneously.

Terminal 1 — Django backend
bash
python manage.py runserver
Confirm the startup line says:

text
Starting ASGI/Daphne version 4.x.x development server at http://127.0.0.1:8000/
If it says WSGIServer instead, daphne is not first in INSTALLED_APPS — see Troubleshooting.

Then open:

Dashboard: http://127.0.0.1:8000/monitoring/dashboard/

Admin: http://127.0.0.1:8000/admin/

API (DRF browsable): http://127.0.0.1:8000/monitoring/api/readings/

You should see the dashboard with the message "Waiting for simulator data..."

Running the Simulator
In a second terminal, from the simulator directory:

bash
cd simulator
python SIMULATOR.py
Expected output:

text
✅ Model loaded successfully from 2v.joblib
A Tkinter window opens showing a 3D cold-chamber digital twin. Within 1 second:

Django terminal begins logging HTTP POST /monitoring/api/readings/ 201

Browser dashboard cards populate with live values

Status banner turns green: ✅ SYSTEM NORMAL

⚠️ If you see ⚠️ Could not load model. Using mock model, the LightGBM model file is missing or was trained with incompatible library versions. The simulator will still run with realistic mock predictions — see Troubleshooting.

Demo Interaction
Use the simulator's operator panel to trigger events:

Action	Expected effect
⚡ POWER: CUT	Compressor stops, temp rises, dashboard → amber → red
🚪 DOOR: OPEN	Faster heat ingress, prediction climbs
❄️ DEFROST: ON	Temporary heat injection
📦 ADD WARM STOCK	Warm load injected, temp spikes
⚠️ SENSOR FAULT: YES	internal_temp_c becomes null in the payload
Restore power + close door	Temp recovers to ~4°C, dashboard → green
API Reference
POST /monitoring/api/readings/
Ingests a temperature reading.

Request body:

json
{
  "room_id": "ROOM_01",
  "internal_temp_c": 4.52,
  "ambient_temp_c": 29.84,
  "ambient_humidity_pct": 60.0,
  "door_open": false,
  "power_status": true,
  "compressor_status": true,
  "predicted_temp_30m": 5.10,
  "risk_level": "SAFE"
}
Response: 201 Created with the persisted row.

Every successful save is automatically broadcast over WebSocket to the dashboard group.

GET /monitoring/dashboard/
Renders the live dashboard HTML. The page opens a WebSocket connection to /ws/dashboard/ and updates in real time as new readings arrive.

WebSocket: ws://127.0.0.1:8000/ws/dashboard/
Receives JSON messages identical in shape to the API payload above. Clients join the dashboard group on connect.

Development
Making changes to models
Whenever you modify a Django model:

bash
python manage.py makemigrations
python manage.py migrate
Commit the generated migration files.

Running tests
bash
python manage.py test
Starting a feature branch
bash
git switch -c feature/<short-description>
git add .
git commit -m "Describe your change"
git push -u origin feature/<short-description>
Then open a pull request on GitHub.

Troubleshooting
daphne.E001: Daphne must be listed before django.contrib.staticfiles in INSTALLED_APPS
daphne must be the first entry in INSTALLED_APPS in config/settings.py. Move it above django.contrib.admin.

TemplateDoesNotExist: monitoring/dashboard.html
Verify the file exists at:

text
monitoring/templates/monitoring/dashboard.html
Not monitoring/templates/dashboard.html and not monitoring/templates/monitoring/templates/dashboard.html.

powershell
Test-Path monitoring\templates\monitoring\dashboard.html
Should return True.

ModuleNotFoundError on simulator startup
Install all simulator dependencies into the same virtualenv:

bash
pip install numpy pandas joblib matplotlib lightgbm scikit-learn requests
ImportError: cannot import name '_api' from partially initialized module 'matplotlib'
The matplotlib installation was interrupted. Clean it up:

powershell
Remove-Item -Recurse -Force .\venv\Lib\site-packages\matplotlib
Remove-Item -Recurse -Force .\venv\Lib\site-packages\matplotlib-*.dist-info
pip install --no-cache-dir matplotlib
⚠️ Could not load model. Using mock model
The .joblib file is missing or incompatible. Options:

Ask the ML team member to provide 2v.joblib trained with the same library versions.

Retrain locally: install matching lightgbm, scikit-learn, pandas, numpy, regenerate the model.

Accept the mock model — it still produces realistic predictions and triggers alerts correctly.

Django starts as WSGI, WebSocket messages never arrive
Confirm:

daphne is installed (pip install daphne)

daphne is first in INSTALLED_APPS

ASGI_APPLICATION = "config.asgi.application" in settings.py

git push -origin main → 'main' does not appear to be a git repository
Typo: use git push origin main (no dash before origin).

Current Implementation Status
✅ Working
Django project with ASGI server (Daphne)

DRF API endpoint for telemetry ingestion

SQLite persistence of TemperatureReading

Django Channels WebSocket broadcast

Live dashboard template with real-time updates

Physics-based Tkinter simulator with LightGBM prediction

End-to-end pipeline: simulator → API → DB → WebSocket → dashboard

🚧 Planned
StorageUnit model with configurable per-unit temperature limits

Server-side ExcursionRecord and Alert models

Temperature history page with charts

Alert acknowledgment workflow

prediction/ app server-side inference endpoint (currently unused)

CSV ingestion endpoint

Authentication and role-based access

Tests (currently empty)

Production configuration (Redis channel layer, PostgreSQL, secrets management)

Team Contributions
This project is maintained by Team NeuroSquad for CodeApex 3.0.

Contributors should:

Create a feature branch from main.

Test locally against the full pipeline (Django + simulator).

Open a pull request with a clear description of the change.

Request review before merging.

Do not commit:

venv/

db.sqlite3

__pycache__/

Large model artifacts (.joblib files over ~50 MB) — provide download instructions instead

Disclaimer
This is an academic software development project. Its predictions, alerts, and excursion records are illustrative and must be validated before any real-world cold-chain safety decisions are based on them. The synthetic data generated by the simulator is not a substitute for real sensor telemetry from validated cold-chain equipment.
