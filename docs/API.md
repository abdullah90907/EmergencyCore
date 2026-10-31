# EmergencyCore 2 — backend first

Flask API for human-reviewed emergency coordination. Replaces the original Gradio prototype with persistent incident tracking, advisory triage, model adapters, weather data, and replayable live events. React + Tailwind can consume this API independently; the frontend is the next phase and is not implemented yet.

## Run on Windows (Python 3.11+)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item backend/.env.example backend/.env
.\.venv\Scripts\python.exe app.py
```

Health: http://127.0.0.1:5000/api/v1/health

If virtualenv creation cannot bootstrap pip, use an existing pip installation:
`python -m pip --python .venv/Scripts/python.exe install -r requirements.txt`

Run checks: `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v`

For a local production-style server: `.\.venv\Scripts\waitress-serve.exe --listen=127.0.0.1:5000 --threads=8 app:app`
Each live event stream occupies a worker thread. Scale streaming separately for many clients.

## Model configuration

Default `AI_PROVIDER=none` disables hosted generation. Local MiniLM semantic analysis remains enabled when installed; keyword triage is retained. Neither is a validated disaster classifier. Responses identify the method, matched terms, limitations, and whether AI was used. Model output is advisory; it cannot automatically verify incidents, reduce rule-derived priority, or dispatch responders.

Hugging Face:

```dotenv
AI_PROVIDER=huggingface
AI_BASE_URL=https://router.huggingface.co/v1
AI_MODEL=your-supported-chat-model-id
AI_VISION_MODEL=your-supported-vision-model-id
AI_API_KEY=your-private-token
```

Choose currently available models for your account from the [Hugging Face provider catalog](https://huggingface.co/docs/inference-providers/en/index). Tokens need inference permission and inference may be billed. Model availability and vision support depend on the provider. No hosted model has been verified with a real account in this workspace.

For an installed open-source model behind a local compatible server:

```dotenv
AI_PROVIDER=compatible
AI_BASE_URL=http://localhost:11434/v1
AI_MODEL=your-installed-model-name
AI_API_KEY=
```

Set a vision model only if your server supports image messages. Uploaded images are validated, resized, converted to JPEG (removing metadata), and sent to the configured provider; they are not stored. Incident text is also sent to the provider when enrichment is enabled. Model calls have timeouts. Text failures preserve local triage with an explicit unavailable status; image failures return 502 instead of fabricated findings.

The hard-coded credential in the original app was removed. Revoke it with its provider. Keep replacement secrets in `.env` and never in frontend code.

## API

All routes use `/api/v1`. Errors use `{"error":{"message":"..."}}`.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | /health | Liveness and database connectivity |
| GET | /capabilities | Configured model/vision/auth capabilities (not provider health) |
| POST | /incidents | Create report and run advisory triage |
| GET | /incidents?status=reported&limit=50&offset=0 | Paginated reports, newest first |
| GET | /incidents/{id} | Report details |
| PATCH | /incidents/{id} | Update status |
| GET | /dashboard | Total, active, and status counts |
| GET | /events | Server-sent events with persistent numeric IDs |
| GET | /weather?latitude=24.86&longitude=67.01 | Real weather provider data |
| POST | /damage-assessments | Multipart `image` upload; requires vision model |

Example report:

```json
{
  "description": "Flood water is rising and two people are trapped near the bridge.",
  "urgency": "high",
  "location": "Karachi",
  "latitude": 24.86,
  "longitude": 67.01
}
```

Urgency: `low`, `medium`, `high`, `critical`. Coordinates are optional but must be provided together. Description length: 10–10000 characters. Image/request limit: 6 MiB; image resolution limit: 20 megapixels.

Update example: `{"status":"verified"}`. Workflow: reported → verified → responding → resolved; reported/verified can also become dismissed. Changes and events are committed atomically. Concurrent status updates use an optimistic status check.

## React + Tailwind integration

Use Vite on `http://localhost:5173` (allowed origin configurable through `CORS_ORIGIN`). Fetch incidents and dashboard metrics on startup, then refresh after `incident.created` / `incident.updated` events. Tailwind styles the React app independently of Flask.

Set `API_TOKEN` to require `Authorization: Bearer <token>` on all routes except health and preflight. Without it, the API is suitable for local development only. Standard browser EventSource cannot set Authorization headers: use a fetch-based SSE client when authentication is enabled. Resume with `Last-Event-ID` or `?after=<id>`; default 0 replays historical events. Persist the latest ID to avoid replaying everything on reconnect. Never put tokens in URLs or expose an operator token in a public client; production needs user authentication and roles.

## Weather and deployment limits

Weather comes from [Open-Meteo](https://open-meteo.com/en/docs), including provider timestamps and units. This is weather model data, not official emergency alerts, flood forecasting, or a verified disaster prediction. Respect provider attribution and applicable usage terms. Upstream outages return 502.

This is an implemented backend foundation, not a deployed emergency service. Before public operation add per-user roles, rate limiting, consent/retention controls, monitoring, TLS, backups, and expert validation. SQLite and threaded SSE suit a small single-host pilot. Multiple deployments need a shared database and event broker. No emergency-service dispatch or official warning integration exists yet.

Next implementation phase: React + Tailwind operations dashboard, map, report intake, review queue, incident timeline, weather panel, and visible model/service status. Then add locally relevant official alerts and responder workflows using verified data sources.

