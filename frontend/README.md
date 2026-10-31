# EmergencyCore frontend

React 19 + Vite + Tailwind CSS 4. Coral, sand and powder blue, glass surfaces, and CSS-driven 3D animation. No external fonts or image services required. Reduced-motion preferences disable animation.

From this directory:

```powershell
npm install
npm run dev
```

Open http://127.0.0.1:5173. Run Flask separately on port 5000. Vite proxies `/api` to Flask. Override `API_PROXY_TARGET` in your shell if your backend runs elsewhere. No secrets belong in Vite environment variables.

`npm run build` produces `dist/`. Production hosting must reverse-proxy `/api` to Flask; Vite's dev proxy is not part of the static build.

## Connected features

- Overview: real incident counts, latest reports, backend and model status.
- Incident desk: search, status filters, report details, human status updates, related-report similarity.
- New report: validated description, urgency, optional paired coordinates; persists through Flask.
- AI intelligence: local text analysis without saving; vision upload enabled only when backend vision is configured.
- Weather watch: coordinate lookup, current modeled weather and hourly precipitation probabilities with attribution.
- Connection settings: optional operator token retained in tab-scoped session storage, never in URLs.

Data refreshes every 12 seconds while the tab is visible. There is no simulated activity. The latest 200 reports are loaded; the dashboard counts all reports, while the critical-priority count is explicitly scoped to those loaded. Report submission does not dispatch emergency services.

## Disaster intelligence workspace

Disaster map navigation opens a MapLibre view of backend-cached roads without external basemap tiles. Select a study region, create/resume a scenario, inspect directed road edges, record blocked/open observations, choose route endpoints and compare modeled travel times. Replay timestamps are UTC. Feed controls ingest USGS/NWS or load the Anchorage historical event. Missing road layers and provider failures are shown as errors. Buildings/facilities overlays and direct SSE consumption remain pending. Route lines currently share an orange style; numeric baseline/adapted results distinguish the comparison. Map rendering requires browser WebGL support.

