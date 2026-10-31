# Neon PostgreSQL migration — November 1, 2026

## Target and result

- Organization: `org-soft-recipe-43518846`.
- Project: `wandering-cherry-47735100`.
- Branch: `production`.
- Provisioned/verified service: **Postgres only**. No Auth, object storage, AI gateway or Functions service was added.
- `neon deploy` authenticated successfully, confirmed the branch already matched the Postgres policy, and pulled `DATABASE_URL`, `DATABASE_URL_UNPOOLED` and `NEON_BRANCH` into ignored root `.env.local`. No connection strings are included in this document.

The installed Neon and neon-postgres plugin skills were consulted. Because the backend is persistent Python/Flask on Waitress, it uses **psycopg 3**, not a JavaScript serverless SQL driver. Runtime uses the pooled URL. Schema operations use the direct URL. Named/positional value binding, row access and transaction contexts are adapted without exposing secrets; SQLite PRAGMAs and AUTOINCREMENT are not executed in the PostgreSQL path. Production startup requires DATABASE_URL and an operator API_TOKEN.

## Code and schema

`database.py` now supports PostgreSQL through psycopg, with parameter binding and explicit transaction/savepoint contexts. Schema migrations remain application-owned source code. SQLite stays available for offline local development/regression tests and is explicitly selected by test database-path overrides. There is no automatic fallback from failed PostgreSQL to SQLite.

Tables verified in Neon:

```text
incidents
 events
 disasters
 ingestion_status
 scenarios
 observations
 route_results
 traffic_snapshots
 region_datasets
 schema_versions
```

The existing observation model stores road/building/facility state by asset ID and scenario. `region_datasets` persists prepared JSON/GeoJSON infrastructure layers; it does not claim unavailable building/facility data exists. The actual prepared public Anchorage road network was uploaded. Request-local caching avoids downloading the same region payload repeatedly inside a single request. Empty/missing layers are still explicit.

Successful future `prepare_region.py` operations save their road/asset snapshots into the configured database. Diskless Render instances can reconstruct map responses from Neon without a local road file. Source graph bytes are preserved so version hashes remain consistent.

`render.yaml` selects Starter compute and removes the persistent disk. Database URLs are secret inputs, model weights are prepared in the build artifact, and /tmp is only a disposable preparation cache. Starter remains a paid compute choice; no paid disk is required. See [deployment instructions](DEPLOYMENT.md).

## Actual command results

```text
npx --yes neon@latest deploy
Auth complete (profile DEFAULT)
Applying to branch production (br-still-glitter-b5jd2ol8)
No changes — branch production already matches the policy.
Utilized services: Postgres
Pulled 3 Neon variables into .env.local
```

```text
python backend/scripts/verify_neon.py
PASS: production PostgreSQL backend started on port 5003
PASS: HTTP incident creation and local triage
PASS: incident/event atomic commit and atomic rollback
PASS: persisted SSE event replay over HTTP
PASS: incident and verified status persisted across backend process restart
PASS: Neon road dataset, scenario, observation and saved blocked-edge route comparison
LIVE NEON VERIFICATION PASSED
```

The verifier used only new synthetic records and removed its own records afterward. It did not copy local incident/scenario data. Run it only with the intended Neon connection configured; it temporarily starts a loopback verification server on port 5003, terminates/restarts that server, and checks persistence over real HTTP. Its requests do not call paid AI providers.

```text
python -m unittest discover -s backend/tests -q
Ran 30 tests in 5.621s
OK
```

```text
npm run build
vite v6.4.5 building for production...
1586 modules transformed.
initial JavaScript: approximately 271 kB
lazy map JavaScript: approximately 1.1 MB
built in 14.32s
```

Vite still emits its large-chunk advisory for the map package. This is not a build failure.

The main backend and frontend were restarted after the migration. The running frontend proxy returned HTTP 200 for `/regions` and `/incidents`; a subsequent `/health` check returned `200 ok`. The first health request during cold startup timed out, so cold-start/network latency remains an operational consideration.

## Failures and limits

1. `npm i -g neon@latest` failed with a Windows npm-directory permission error. The user-requested npx fallback worked.
2. `neon init` created the link/config but reported incomplete agent-skill setup under Node 20.20.2; the skills helper needs Node 22.20+. A separate temporary Node 22 skills attempt failed with a Windows helper/cache error. Existing installed plugin skills were read and used. Node 22.20+ is now declared in package metadata. The system Node installation was not globally replaced.
3. The first root build attempt ran npm ci while Vite held a native dependency DLL, causing EPERM. After stopping Vite and restoring dependencies, root `npm run build` passed. Root `npm run setup` now performs installation separately.
4. Automatic approval review rejected a separate attempt to copy existing local incident/scenario records to Neon because that sensitive payload transfer was not explicitly authorized. It was not executed or bypassed. Schema migration, synthetic verification and the public prepared road dataset are complete. Existing local SQLite records remain untouched and unexported.
5. No Render or Vercel cloud deployment, Git push, paid service plan change or unattended ingestion-worker provisioning was performed in this migration.

## Operator next steps

- Set both Neon URLs privately in Render, plus API_TOKEN, provider keys and exact CORS_ORIGIN.
- Configure Vercel's public VITE_API_BASE_URL and rebuild there.
- Upgrade the development CLI runtime to Node 22.20+ to avoid engine warnings and retry optional agent-skill installation if desired.
- Decide separately whether existing local reports, events and scenarios should be transferred into Neon. That requires explicit approval and a reviewed conflict/backup strategy; the database migration does not silently upload them.
- Use direct-connection pg_dump/Neon restore facilities for backups. The old SQLite backup script refuses to operate when PostgreSQL is configured.

## Fresh Neon demonstration

After verification, one official Anchorage earthquake was fetched directly from public USGS and a new simulated routing demonstration was generated in Neon (scenario 25910a76-c16e-489c-a398-b70a283ce504). Actual output: baseline 933.14 seconds, adapted 939.17 seconds, delay 6.03 seconds. This was a new public-data/simulation seed, not a copy of existing local incidents or scenarios.

