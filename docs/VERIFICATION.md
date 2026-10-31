# Verified application results — October 31, 2026

The browser audit reproduced a blank disaster map. Vite failed to load MapLibre 6 web workers; an explicit Vite worker URL now packages and serves the worker. Map readiness/cancellation was also corrected. The repaired browser rendered 2,557 visible road features from the 5,365-edge Anchorage dataset.

The disaster page now includes Load routing demonstration, different colors for baseline/adapted routes, cached official earthquake evidence, larger control text, and the correct page description. The saved demonstration uses actual current OSM roads and a simulated closure, not a documented historical closure. Results: baseline 933.14 s; adapted 939.17 s; delta 6.03 s; one excluded edge. UI rounds these to 15.6 min, 15.7 min and 6.0 sec.

Browser verification passed at 1440 px desktop and 390 px phone width, with no page errors and no horizontal overflow. Screenshots: [desktop routing](evidence/routing-desktop.png), [phone routing](evidence/routing-mobile.png).

A real request submitted through the AI intelligence form returned HTTP 200, category flood, critical keyword priority, local semantic inference available, and a 1,577-character advisory from Groq qwen/qwen3.8-27b. The input explicitly identified itself as a test scenario. No incident was saved. Advisory markdown is now formatted safely as React text/headings within a bounded scroll panel, with actual provider/model shown. [AI result screenshot](evidence/groq-analysis.png).

Gemini fallback was disabled in the private environment at the user's request. The local Flask server was restarted to load current credentials; changing .env alone cannot update an already-running server.

Backend regression: all 25 tests passed. Production frontend build passed, including the emitted map worker asset. Vite reports a large-bundle advisory; code splitting remains a performance improvement.

Remaining limitations: real buildings/facility layer download is incomplete; Alaska traffic matching does not automatically establish a road closure; candidate routes are not safety guarantees; current road data and simulated closures are not an exact 2018 reconstruction. Full end-to-end browser tests for every replay/edit combination and facility workflow are not claimed.


## Map-workspace root-cause follow-up

Replaced the map workflow with separate layer readiness and operation states, cancellation of obsolete region loads, cleared scenario/route/marker state on region change, full-dataset closure filtering, visible endpoint markers and distinct baseline/adapted/blocked layers. Unprepared regions no longer attempt routing or scenario creation. The sidebar scrolls without shrinking its cards. The map resizes and refits its last region/route bounds when the viewport changes. Route results invalidate and recalculate when replay time or road state changes.

Added an attributed, configurable OSM raster basemap for geographic context. Automated map tests block public tile requests to avoid automated tile pan/zoom; external basemap delivery is not claimed as verified by those tests. Cached overlay operations work independently of the basemap. For larger production traffic, configure a suitable tile provider through VITE_BASEMAP_TILE_URL.

The map now loads on demand. Production initial JavaScript is approximately 270 kB rather than the previous 1.35 MB monolithic bundle; the separate map chunk remains approximately 1.1 MB. This is a build-size observation, not a network-speed benchmark.

Browser regression checks cover saved demo, endpoint pins, unavailable LA controls, absence of stale results/markers, rapid region switching, replay before closure (zero excluded edges/zero delay), scrolling sidebar at 600px height, and no horizontal overflow at 390px width. Backend: 25 tests pass; production build passes. Map screenshots in docs/evidence/workspace-* show automated offline-overlay QA, not externally downloaded basemap tiles.

