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
