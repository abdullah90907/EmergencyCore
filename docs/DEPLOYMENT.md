# Render + Vercel deployment with Neon

This guide supersedes the previous SQLite/persistent-disk instructions. See [Neon migration and verification](NEON.md) for the actual project, tests and outstanding local-record transfer decision.

## Render backend

The root `render.yaml` selects a **Starter Python web service** with **no disk**. Starter is still paid compute; the persistent-disk charge/requirement has been removed. A free plan is not selected implicitly: cold-start/sleep behavior and CPU/memory limits must suit your pilot. No Render resource has been deployed by this migration.

- Root directory: `backend`.
- Build: `pip install -r requirements-models.txt -r requirements-geo.txt && python scripts/setup_model.py`.
- Start: `python serve.py`.
- Health: `/api/v1/health`.
- Runtime binds `0.0.0.0:$PORT`.

Configure these **Render secrets**, not Vercel variables:

```dotenv
APP_ENV=production
DATABASE_URL=YOUR_NEON_POOLED_CONNECTION_STRING
DATABASE_URL_UNPOOLED=YOUR_NEON_DIRECT_CONNECTION_STRING
API_TOKEN=YOUR_PRIVATE_OPERATOR_SECRET
GROQ_API_KEY=YOUR_GROQ_KEY
ALASKA_511_API_KEY=YOUR_ALASKA_KEY
CORS_ORIGIN=https://YOUR-PROJECT.vercel.app
AI_PROVIDER=groq
AI_FALLBACK_ENABLED=false
```

The database URLs are already pulled locally into ignored root `.env.local`. Transfer their values through Render's private settings yourself; do not commit them or put them in screenshots. Preserve Neon-supplied TLS options. Runtime traffic uses the pooled connection; additive schema creation/migrations use the direct connection where supplied. Production startup rejects missing DATABASE_URL or API_TOKEN.

MiniLM weights are downloaded during the build into the service's build artifact, not a persistent disk. Restart does not depend on a new model download. The build requires public Hugging Face availability. Region JSON/GeoJSON datasets are durable in PostgreSQL's `region_datasets`; `/tmp` files are only optional preparation caches. The prepared Anchorage roads have been uploaded already. Missing building/facility layers are still reported missing.

To prepare another region, run `python scripts/prepare_region.py REGION_ID` in a trusted environment with the same Neon variables. Successful downloads are persisted into PostgreSQL. `--assets` also attempts mapped buildings/facilities. Replacing a road snapshot invalidates pinned scenarios; do not replace production graphs casually.

Neon makes a shared database possible for a separate ingestion worker. Run `python scripts/ingest.py --source live --watch` in a separately managed worker with the same DATABASE_URL and required provider keys, if unattended ingestion is wanted. That worker is **not** provisioned by this Blueprint. The web app still supports manual authenticated ingestion. Direct frontend SSE consumption remains unimplemented.

## Vercel frontend

- Root directory: `frontend`.
- Framework: Vite.
- Node: 22.20+.
- Install: `npm ci`.
- Build: `npm run build`.
- Output: `dist`.
- Public environment: `VITE_API_BASE_URL=https://YOUR-API.onrender.com` (origin only).

Set Render's CORS_ORIGIN to the exact deployed frontend origin. Redeploy the frontend after changing VITE_API_BASE_URL. Never place DATABASE_URL, Groq/Gemini/Alaska keys, or API_TOKEN in VITE_* variables. Use the app's Connection settings to enter the operator token on a trusted device. Preview deployment origins are not wildcard-authorized.

## Operations and acceptance

1. Check the HTTPS backend health endpoint.
2. Open the Vercel app, set the operator token, create a labelled test report and reload it.
3. Restart the backend and confirm the report/history remains.
4. Check the local model, hosted advisory and weather independently.
5. Confirm prepared regions report ready even without local road files.
6. Run a scenario, add a simulated blocked edge, compare routes and inspect the saved result.
7. Check ingestion freshness; it is not automatic merely because a database exists.

Use Neon backups/restore facilities or `pg_dump` with the **direct** connection for backups. The SQLite backup script explicitly refuses PostgreSQL configurations. Never copy a local SQLite file and assume it backs up Neon.

Existing local SQLite records were not exported to Neon. That transfer is a separate operator decision. Production has the schema and prepared public road data; verification records were synthetic and cleaned up.

This is an access-controlled pilot, not public multiuser emergency infrastructure. Per-user roles, rate limiting, monitoring, retention policies and validated operational data remain necessary before broader operation. Candidate routes are not safety guarantees.
