# Disaster intelligence backend — implementation and handoff

The existing Flask APIs, incident tables, MiniLM inference and React interface are preserved. This phase adds backend geospatial intelligence; the existing frontend does not yet contain a MapLibre disaster/replay screen.

## Implemented

- Additive SQLite migration with schema tracking; original incidents and events are retained.
- Public USGS M2.5+ day-feed ingestion, official Anchorage 2018 event detail import, and ShakeMap/PAGER product references. USGS is a global feed; US study areas can be selected using supplied geometries. Lower-magnitude earthquakes are not included in this live feed.
- NWS active-alert ingestion with source/expiry timestamps, cancelled/expired and absent-from-latest-feed handling, ingestion freshness records and cached-data preservation on upstream failures.
- Configurable study regions, cached actual OSM driving networks, building footprints and mapped facilities. Default regions are Anchorage and central Los Angeles, not entire metropolitan coverage.
- Nearest-road matching in a local projected CRS with bounded distance and an explicit unverified mapping label.
- Scenario-isolated asset observations with Official / Community-Reported / AI-Estimated / Simulated evidence, source links, verification, observation and recording timestamps.
- Simulation, historical and live scenario modes; timestamp-based reconstruction, reopening events, graph-version pinning and persisted route comparisons.
- Directed multigraph routing with independent parallel edges, explicitly blocked-edge exclusion, up to three node-path alternatives, endpoint snapping, unavailable facility handling and modeled travel times.
- User-defined polygon exposure intersections with mapped assets, clearly separate from confirmed damage or predictive AI output.
- Evidence-linked deterministic response summaries. No generated claims of dispatch, verification or safety.
- Alaska 511 adapter with a private backend key, current snapshot storage and candidate road matches. It deliberately does not auto-close a road based on an unverified nearest-point match.
- Separate ingestion worker, OSM preparation, historical CSV observation importer and reproducible Anchorage disruption demo. New records emit events through the existing replayable SSE table.

## Install and run

From the project root:

```powershell
python -m pip --python .venv/Scripts/python.exe install -r backend/requirements-geo.txt
# Keep an existing backend/.env; merge new settings from backend/.env.example.
.\.venv\Scripts\python.exe backend/scripts/prepare_region.py anchorage --assets
.\.venv\Scripts\python.exe backend/scripts/ingest.py --source anchorage-2018
.\.venv\Scripts\python.exe backend/scripts/ingest.py --source live
.\.venv\Scripts\python.exe backend/scripts/demo_anchorage.py
.\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:5000 --threads=8 app:app
```

Live periodic updates run in **one separate process**, never once per Flask worker:

```powershell
.\.venv\Scripts\python.exe backend/scripts/ingest.py --source live --watch
```

The interval defaults to 300 seconds and is bounded to at least 60. One-shot ingestion is the default; importing the Flask app never starts network calls or a scheduler. Use Ctrl+C to stop the worker. Run a separate `--source alaska511 --watch` worker only after configuring the key. No perpetual worker is automatically installed as a system service.

Road snapshots are reused by default. `--refresh-roads` explicitly replaces one and invalidates scenarios pinned to the old graph; create new scenarios after replacement. Download failures do not fabricate roads or assets. `--overpass-url https://overpass.private.coffee/api` selects an alternative public endpoint when the default is overloaded. For sustained operation, use a local extract or your own Overpass service rather than repeatedly downloading.

## Configuration and assistance needed

```dotenv
GEO_DATA_DIR=data
ALASKA_511_API_KEY=
NWS_USER_AGENT=EmergencyCore-local-prototype
INGEST_INTERVAL_SECONDS=300
REGIONS_FILE=
```

Paths are backend-relative unless absolute. Put the Alaska developer key in `backend/.env`, never chat, source code, frontend environment variables, or URLs shown to users. The upstream Alaska endpoint requires a key query parameter; this app suppresses upstream exception strings to avoid leaking it. Register at [Alaska 511 developer documentation](https://511.alaska.gov/developers/doc). The live adapter has not been account-tested without that key.

USGS, NWS and public OSM downloads do not require paid AI accounts. NWS requires an identifying User-Agent and recommends a project URL/contact. Replace the local prototype identifier with your real project contact when available: [NWS API documentation](https://www.weather.gov/documentation/services-web-api).

For historical damage, supply the original Alaska DOT document or a verified replacement/source dataset. The PDF URL in the specification returned 404 during implementation. An alternative research source is [USGS Ground Failure Triggered by Shaking report](https://pubs.usgs.gov/of/2020/1043/ofr20201043.pdf), but its observations still need reviewed coordinates, dates and edge mapping. No specific historical road closure has been invented or automatically extracted from narrative text.

### Custom regions

Set REGIONS_FILE to a backend-relative JSON file. Entries extend/override defaults:

```json
{
  "custom-area": {
    "name": "Custom study area", "state": "AK",
    "center": [-149.90, 61.21],
    "bbox": [-149.96, 61.18, -149.82, 61.24],
    "metric_crs": "EPSG:32606"
  }
}
```

Bounds use `[west, south, east, north]`; coordinates are `[longitude, latitude]`. Pick the correct metric projected CRS for the study area. Antimeridian-spanning study bounds are not supported. Changing a region bbox requires an explicit new road download.

## New API contract

All routes begin `/api/v1`, use existing error envelopes, and inherit existing optional bearer auth. Set API_TOKEN before exposing ingestion or scenario mutations outside a trusted machine.

| Method | Path | Purpose |
|---|---|---|
| GET | `/regions` | Study areas and cached layer readiness |
| GET | `/regions/{id}` | Bounds, CRS, graph version and counts |
| GET | `/regions/{id}/layers/roads?bbox=w,s,e,n` | GeoJSON road edges and graph version |
| GET | `/regions/{id}/layers/assets` | Buildings/facilities or explicit missing-layer notice |
| POST | `/regions/{id}/match-road` | `{ "coordinates": [lon,lat], "max_distance_m": 100 }` |
| POST | `/regions/{id}/exposure` | `{ "hazard_geometry": { "type":"Polygon", "coordinates":[...] } }` |
| POST | `/ingestion/{source}` | `usgs`, `nws`, `anchorage-2018`, or `alaska511` |
| GET | `/ingestion/status` | Last attempts, successful fetch times, counts, errors |
| GET | `/disasters?mode=historical&source=USGS` | Normalized events; supports limit/offset |
| GET | `/disasters/{provider:id}` | Event detail with product references |
| GET/POST | `/scenarios` | List/create isolated scenario |
| GET | `/scenarios/{id}?at=ISO_TIMESTAMP` | Asset states reconstructed at a replay time |
| GET/POST | `/scenarios/{id}/observations` | Timeline or new observation |
| GET/POST | `/scenarios/{id}/routes` | Saved results or calculate route comparison |
| GET | `/scenarios/{id}/decision?at=ISO_TIMESTAMP` | Evidence-linked summary |
| GET | `/regions/{id}/traffic` | Cached Alaska events and unverified matching candidates |

Each ingestion source has a minimum 60-second retry interval. This is a pilot cooldown, not a distributed rate-limiting system. NWS `active` reflects the cached snapshot, status and expiry; inspect fetched_at and ingestion/status before treating it as current.

Create a scenario:

```json
{"name":"Anchorage disruption test","region_id":"anchorage","mode":"simulation","disaster_id":"usgs:ak018fcnsk91"}
```

Add an observation (obtain a real asset_id from the layer):

```json
{"asset_id":"u:v:key","state":"blocked","observed_at":"2018-11-30T18:00:00Z","note":"Simulated closure for route comparison"}
```

States: `open`, `blocked`, `damaged`, `unavailable`. A `damaged` road is not automatically considered impassable. Blocked/unavailable edges are excluded; an explicit open observation reopens the selected edge. Direction and parallel edges remain separate. To block both directions, record every affected directed edge explicitly after checking its geometry.

Public API observations cannot promote themselves to Official or reviewed by passing extra fields. Simulation mode always labels them Simulated; historical/live manual reports are Community-Reported. Official evidence enters through a trusted local importer, and remains unverified unless the operator explicitly attests review.

Route request:

```json
{"origin":[-149.92,61.21],"destination":[-149.88,61.22],"at":"2018-11-30T18:30:00Z"}
```

Or replace destination coordinates with `destination_asset_id` for a mapped facility. Unknown facility state stays unknown. A facility marked unavailable/blocked returns no usable adapted destination route. Endpoints more than 1 km from the cached road graph are rejected. Results contain baseline/adapted GeoJSON routes, alternatives, excluded evidence, time difference, snap distances and graph version. There is no live-traffic, turn-restriction, vehicle-clearance or guaranteed-safe evacuation model.

### Historical evidence import

CSV columns: `asset_id,state,observed_at,source_url,note,evidence`. Dates need an explicit timezone. Official observations require an HTTPS source reference.

```powershell
.\.venv\Scripts\python.exe backend/scripts/import_observations.py SCENARIO_ID path/to/reviewed-evidence.csv --reviewed
```

The batch is transactional. Re-running the same file creates new audit observations; do not reimport unintentionally. Only use --reviewed after checking the original evidence and road mapping. The historical replay is an observation-time reconstruction, not a simulation of information known to responders at each moment; recorded_at separately preserves when this system received the evidence.

## Remaining phases and explicit limits

- MapLibre layers, map interaction, frontend replay controls and SSE consumption are not implemented in this backend-only phase.
- ShakeMap/PAGER metadata and download references are imported; raster/MMI sampling and probabilistic structural damage inference are not implemented.
- The Anchorage demo uses the official earthquake context and a modern road graph, with an explicitly simulated closure. It is not claimed to reproduce documented 2018 damage.
- CAL FIRE DINS Los Angeles 2025 validation and GDACS remain later integrations; LA is currently a configured study region, without downloaded layers.
- The [HOTOSM model](https://huggingface.co/hotosm/earthquake-damage-assessment-model) requires aligned post-disaster RGB GeoTIFF imagery and building footprints (optional aligned pre-disaster imagery). It is not a generic photo model; its model card declares noncommercial share-alike terms. These input data are required before integrating its inference pipeline. Existing optional hosted photo analysis remains unchanged.
- Routing scans cached nodes and uses bounded prototype shortest paths. Larger regions need spatial indexes, request limits, worker queues and performance tuning.
- US-wide monitoring uses provider data and configurable study-area geometry, not a US boundary dataset; the raw USGS feed includes earthquakes outside the US.
- Single operator token is inherited from the prototype. Per-user roles and durable operator audit identities are still needed before public multiuser deployment.

## Verification

Implementation check: all 19 tests pass. Live one-shot ingestion returned 38 USGS earthquakes and 439 NWS alerts; these are cached snapshots, not a promise of continuous freshness. The imported Anchorage event is magnitude 7.1 and includes four ShakeMap product references. The actual cached road graph contains 2,116 nodes and 5,365 directed edges. The real-road simulated-closure demo changed modeled time from 933.14 s to 939.17 s and excluded the blocked edge. Building/facility download attempts encountered capacity errors/timeouts on two public OSM servers; this layer is currently missing locally and the API reports assets_ready=false. Asset-state and exposure behavior is covered by labelled test fixtures, not claimed as validated real building damage.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Tests cover existing incident/model functions, migrations, directed/parallel edge exclusion, full disconnection, isolated scenarios, reopening by replay timestamp, facility unavailability, graph-version mismatch, layer matching, exposure, ingestion idempotency/outages, expired alerts and auth on new endpoints. `demo_anchorage.py` additionally exercises actual cached OSM roads, stores before/after routes and asserts the selected blocked edge is absent from the adapted route. Its output is saved in `backend/data/anchorage/demo-result.json`.
