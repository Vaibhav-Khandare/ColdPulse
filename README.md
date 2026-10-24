# ColdPulse

**AI-Powered Cold Chain Monitoring and Predictive Temperature Excursion Early Warning System**

## Overview

ColdPulse is a Django-based project designed to support cold-chain monitoring, temperature excursion detection, and predictive early warning.

## Technology Stack

- Python
- Django
- HTML, CSS, and JavaScript
- SQLite for local development
- Pandas, NumPy, and scikit-learn when required for data analysis and machine learning

## Project Structure

```text
ColdPulse/
├── config/
├── monitoring/
├── prediction/
├── templates/
├── static/
├── datasets/
├── manage.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3
- Git
- A GitHub account

## Setup

### 1. Clone the repository

```bash
git clone <https://github.com/Vaibhav-Khandare/ColdPulse.git>
cd ColdPulse
```

### 2. Create a virtual environment

Windows:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Apply database migrations

```bash
python manage.py migrate
```

### 5. Run the development server

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000/monitoring/ in your browser.

## Applications

- **Monitoring:** Temperature readings, storage units, excursion records, and alerts.
- **Prediction:** Temperature excursion prediction and early-warning logic.

## Development

Create and commit migrations whenever you modify Django models:

```bash
python manage.py makemigrations
python manage.py migrate
```

## Team Contributions

Contributors should create feature branches, test their changes, and open pull requests for review.

## Disclaimer

This is a software development project. Its predictions and alerts must be validated before any real-world cold-chain safety decisions are based on them.