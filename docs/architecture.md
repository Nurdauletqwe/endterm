# As-built architecture — DocRequest

![Architecture](../architecture.png)

- Client: browser on a phone or PC (HTML, Bootstrap, JavaScript); the student page asks the server for new statuses every 3 seconds.
- Network: internet, all traffic over HTTPS (TLS).
- Server: Flask app (main.py) on Render, free plan: log-in, roles (403 for other roles), static media, IoT API with a device token (401 without it).
- Database: Render PostgreSQL, region Frankfurt (EU); passwords stored as bcrypt hashes.
- Smart cabinets: simulated by simulate_lockers.py (HTTP POST with X-Device-Token).

## Changes from Stage 1
| Stage 1 plan | As built | Reason |
|---|---|---|
| Firebase | Flask server | SQL, roles and password hashing from Assignment 3 |
| Cloud Firestore | PostgreSQL | JOIN and GROUP BY for data analysis |
| Firebase Hosting | Render with HTTPS | Runs Python apps, free HTTPS |
| Real-time Firestore | Polling every 3 s | Simple in Flask, within the 5 s criterion |
