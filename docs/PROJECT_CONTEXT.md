# EmergencyCore 2.0 codebase context

EmergencyCore is an operator decision-support prototype for incident triage, disaster context and infrastructure scenario routing. It does not dispatch responders, verify casualties or certify buildings/routes as safe.

## Architecture

React 19, Tailwind 4, Vite and MapLibre frontend: App.jsx owns incidents, intelligence, weather and connection settings; DisasterWorkspace.jsx owns maps, observations, replay and routing. api.js calls /api/v1 at VITE_API_BASE_URL. connection.js manages session or opt-in remembered bearer access, scoped to the backend origin. Never embed server secrets in frontend builds.

Flask application factory: backend/emergencycore/__init__.py. Production entry: backend/serve.py using Waitress and PORT. run.py is development-only. api/routes.py serves reporting, AI, weather and events; api/intelligence.py serves regions, feeds, scenarios and routes. Services contain business logic.

## Persistence and data

Production uses psycopg PostgreSQL on Neon; SQLite remains available locally. database.py selects the driver; migrations.py adds intelligence schema. Production requires DATABASE_URL and API_TOKEN. Pooled URLs serve runtime requests; direct URLs serve maintenance. Never introduce SQLite-only SQL into the PostgreSQL path.

Tables: incidents, events, disasters, ingestion_status, scenarios, observations, route_results, traffic_snapshots, region_datasets and schema_versions. Incident changes and event history must remain atomic. Regional OSM snapshots are persisted in Postgres and restored to temporary caches. Routing preserves directed parallel edges, applies explicit observations and compares modeled travel times. Replay uses observation timestamps. Label simulated evidence accurately; never invent missing geographic layers.

## Models and providers

Local MiniLM ONNX embeddings provide category similarity and related reports, not confidence probabilities. Independent keyword rules flag critical language. Optional Groq text/vision advisory and optional Gemini fallback are environment-configured. Inspect config.py and provider services before changing model behavior; configured IDs do not establish live provider availability. Missing hosted AI must preserve local output. README contents are not automatically supplied to inference prompts.

USGS and NWS provide official source context; Alaska 511 requires a key; Open-Meteo supplies weather model data. Ingestion runs explicitly or through a separate worker. The frontend polls; an SSE endpoint exists but frontend SSE consumption is pending.

## Authentication and verification

Shared operator bearer authentication is implemented. Individual accounts, roles and login sessions are future work. Browser persistence is opt-in; Forget connection clears persistent and session access.

Run npm run build from root. Run python -m unittest discover -s backend/tests -v using the configured Python environment; model-dependent tests need downloaded weights. Read backend/scripts/verify_neon.py before running: it writes temporary verification records to the configured database. Do not export private local incidents without authorization.

Consult docs/DEPLOYMENT.md and docs/NEON.md. Do not commit secrets, env files, model weights or private databases. Screenshots document a capture, not current provider health.
