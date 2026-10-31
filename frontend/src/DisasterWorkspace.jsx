import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { MapPin, Route, Layers, Play, RotateCcw, AlertCircle, CheckCircle2 } from 'lucide-react';
import { api } from './api';
import './disaster.css';
maplibregl.setWorkerUrl(workerUrl);
const empty = () => ({ type: 'FeatureCollection', features: [] });
const feature = geometry => ({ type: 'Feature', geometry, properties: {} });
const coordsOf = route => route?.geometry?.coordinates?.flat() || [];
const stamp = value => new Date(value).toLocaleString([], { timeZone: 'UTC', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) + ' UTC';

export default function DisasterWorkspace() {
  const container = useRef(null), map = useRef(null), roads = useRef(empty()), markers = useRef([]), clicks = useRef(() => {}), generation = useRef(0), fitTarget = useRef([]);
  const [ready, setReady] = useState(false), [regions, setRegions] = useState([]), [region, setRegion] = useState('anchorage');
  const [loading, setLoading] = useState(true), [working, setWorking] = useState(false), [error, setError] = useState(''), [mapError, setMapError] = useState('');
  const [mode, setMode] = useState('simulation'), [scenarios, setScenarios] = useState([]), [scenario, setScenario] = useState(null);
  const [events, setEvents] = useState([]), [observations, setObservations] = useState([]), [states, setStates] = useState({});
  const [origin, setOrigin] = useState(null), [destination, setDestination] = useState(null), [tool, setTool] = useState('inspect');
  const [selected, setSelected] = useState(null), [result, setResult] = useState(null), [at, setAt] = useState('2018-11-30T18:30');
  const [baseVisible, setBaseVisible] = useState(true), [networkVisible, setNetworkVisible] = useState(true);
  const study = regions.find(r => r.id === region), available = Boolean(study?.network_ready);
  const demoScenario = scenarios.find(s => s.region_id === region && s.name.includes('SIMULATED road disruption'));
  const asOf = () => mode === 'live' ? undefined : at ? new Date(at + 'Z').toISOString() : undefined;

  async function run(fn) {
    const version = generation.current;
    setWorking(true); setError('');
    try { await fn(version); } catch (e) { if (version === generation.current) setError(e.message); }
    finally { if (version === generation.current) setWorking(false); }
  }
  function setGeo(id, data) { map.current?.getSource(id)?.setData(data); }
  function clearRoutes() { setResult(null); setGeo('baseline', empty()); setGeo('adapted', empty()); }
  function fit(coordinates) {
    if (!coordinates.length || !map.current) return;
    fitTarget.current = coordinates;
    const bounds = coordinates.reduce((b, c) => b.extend(c), new maplibregl.LngLatBounds(coordinates[0], coordinates[0]));
    map.current.fitBounds(bounds, { padding: 55, maxZoom: 15, duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 450 });
  }
  function showRoutes(r, zoom = true) {
    setGeo('baseline', { type: 'FeatureCollection', features: r.baseline ? [feature(r.baseline.geometry)] : [] });
    setGeo('adapted', { type: 'FeatureCollection', features: r.adapted ? [feature(r.adapted.geometry)] : [] });
    setResult(r); if (zoom) fit(coordsOf(r.baseline));
  }
  async function readScenario(s, time, version) {
    const [snapshot, history] = await Promise.all([api(`/scenarios/${s.id}${time ? '?at=' + encodeURIComponent(time) : ''}`), api(`/scenarios/${s.id}/observations`)]);
    if (version !== generation.current) return;
    setStates(snapshot.asset_states); setObservations(history.items);
  }

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api('/regions', { signal: controller.signal }), api('/scenarios', { signal: controller.signal }), api('/disasters?mode=historical', { signal: controller.signal })])
      .then(([r, s, d]) => { setRegions(r.items); setScenarios(s.items); setEvents(d.items); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    let m;
    try {
      m = new maplibregl.Map({ container: container.current, center: [-149.9, 61.218], zoom: 12, attributionControl: false,
        style: { version: 8, sources: { basemap: { type: 'raster', tiles: [import.meta.env.VITE_BASEMAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' } }, layers: [{ id: 'paper', type: 'background', paint: { 'background-color': '#edf1f2' } }, { id: 'basemap', type: 'raster', source: 'basemap', paint: { 'raster-saturation': -0.7, 'raster-opacity': 0.82 } }] } });
      map.current = m;
      m.addControl(new maplibregl.NavigationControl(), 'top-right');
      m.addControl(new maplibregl.AttributionControl({ compact: false }), 'bottom-right');
      m.addControl(new maplibregl.ScaleControl(), 'bottom-left');
      m.on('error', e => setMapError(e.sourceId === 'basemap' ? 'Background map unavailable. Cached roads and routing remain available.' : 'A map layer failed to render. Try reloading the workspace.'));
      m.once('load', () => {
        for (const [id, color, width, dash] of [['roads', '#647d90', 1.3], ['baseline', '#2473c1', 7, [2, 1.5]], ['adapted', '#f26b3f', 4.5], ['closures', '#bd3d32', 7], ['selected', '#1e3c52', 5]]) {
          m.addSource(id, { type: 'geojson', data: empty() });
          m.addLayer({ id, type: 'line', source: id, layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': color, 'line-width': width, ...(dash ? { 'line-dasharray': dash } : {}) } });
        }
        setReady(true);
      });
      m.on('click', e => clicks.current(e));
      const resize = new ResizeObserver(() => {
 m.resize(); const points = fitTarget.current;
 if(points.length) m.fitBounds(points.reduce((b,c)=>b.extend(c),new maplibregl.LngLatBounds(points[0],points[0])),{padding:45,maxZoom:15,duration:0});
 }); resize.observe(container.current);
      return () => { resize.disconnect(); markers.current.forEach(x => x.remove()); markers.current = []; m.remove(); map.current = null; };
    } catch { setMapError('Interactive maps require WebGL. Enable browser hardware acceleration or use another browser.'); setLoading(false); }
  }, []);

  useEffect(() => {
    if (!ready || !study) return;
    const version = ++generation.current, controller = new AbortController();
    setError(''); setWorking(false); setLoading(available); setScenario(null); setSelected(null); setStates({}); setObservations([]); setOrigin(null); setDestination(null); setTool('inspect'); clearRoutes();
    roads.current = empty(); for (const id of ['roads', 'closures', 'selected']) setGeo(id, empty());
    fitTarget.current = [];
    map.current.jumpTo({ center: study.center, zoom: 12 });
    if (available) api(`/regions/${region}/layers/roads`, { signal: controller.signal }).then(data => {
      if (version !== generation.current) return;
      roads.current = data; setGeo('roads', data); fit(data.features.flatMap(f => f.geometry.coordinates)); setLoading(false);
    }).catch(e => { if (!controller.signal.aborted && version === generation.current) { setError(e.message); setLoading(false); } });
    return () => controller.abort();
  }, [region, study, ready, available]);

  useEffect(() => { if (ready) map.current.setLayoutProperty('basemap', 'visibility', baseVisible ? 'visible' : 'none'); }, [baseVisible, ready]);
  useEffect(() => { if (ready) map.current.setLayoutProperty('roads', 'visibility', networkVisible ? 'visible' : 'none'); }, [networkVisible, ready]);
  useEffect(() => {
    setGeo('closures', { type: 'FeatureCollection', features: roads.current.features.filter(f => ['blocked', 'unavailable'].includes(states[String(f.id)]?.state)) });
  }, [states, ready]);
  useEffect(() => {
    markers.current.forEach(x => x.remove()); markers.current = [];
    for (const [position, label] of [[origin, 'A'], [destination, 'B']]) if (position && map.current) {
      const el = document.createElement('div'); el.className = `route-pin pin-${label}`; el.textContent = label; el.setAttribute('aria-label', label === 'A' ? 'Route origin' : 'Route destination');
      markers.current.push(new maplibregl.Marker({ element: el }).setLngLat(position).addTo(map.current));
    }
  }, [origin, destination]);

  clicks.current = e => {
    if (!available || loading || working) return;
    if (tool === 'origin') { clearRoutes(); setOrigin([e.lngLat.lng, e.lngLat.lat]); setTool('destination'); return; }
    if (tool === 'destination') { clearRoutes(); setDestination([e.lngLat.lng, e.lngLat.lat]); setTool('inspect'); return; }
    const hits = map.current.queryRenderedFeatures([[e.point.x - 5, e.point.y - 5], [e.point.x + 5, e.point.y + 5]], { layers: ['roads'] });
    if (!hits.length) return;
    const hit = roads.current.features.find(f => String(f.id) === String(hits[0].id));
    if (hit) { setSelected(hit); setGeo('selected', { type: 'FeatureCollection', features: [hit] }); }
  };

  async function calculate(s = scenario, time = asOf(), version = generation.current) {
    const r = await api(`/scenarios/${s.id}/routes`, { method: 'POST', body: JSON.stringify({ origin, destination, at: time }) });
    if (version === generation.current) showRoutes(r, false);
  }
  async function loadDemo() { await run(async version => {
    const [s, history] = await Promise.all([api(`/scenarios/${demoScenario.id}`), api(`/scenarios/${demoScenario.id}/routes`)]);
    if (version !== generation.current) return;
    const r = history.items.find(x => x.excluded_edges.length) || history.items[0];
    if (!r) throw new Error('This saved demonstration has no route results.');
    setScenario(s); setMode(s.mode); setAt(r.as_of.slice(0,16));
    const coordinates = coordsOf(r.baseline); setOrigin(coordinates[0]); setDestination(coordinates.at(-1));
    await readScenario(s, r.as_of, version); if (version === generation.current) showRoutes(r);
  }); }
  async function create() { await run(async version => {
    const s = await api('/scenarios', { method: 'POST', body: JSON.stringify({ name: `${study.name} ${mode}`, region_id: region, mode }) });
    if (version !== generation.current) return;
    setScenario(s); setScenarios(items => [s, ...items]); setStates({}); setObservations([]); clearRoutes();
  }); }
  async function resume(id) { await run(async version => {
    const s = await api(`/scenarios/${id}`); if (version !== generation.current) return;
    setScenario(s); setMode(s.mode); clearRoutes(); setOrigin(null); setDestination(null);
    await readScenario(s, s.mode === 'live' ? undefined : asOf(), version);
  }); }
  async function changeState(state) { await run(async version => {
    const time = asOf();
    await api(`/scenarios/${scenario.id}/observations`, { method: 'POST', body: JSON.stringify({ asset_id: String(selected.id), state, observed_at: time, note: 'Operator-selected directed edge from map; verify extent and direction before operational use.' }) });
    await readScenario(scenario, time, version);
    if (origin && destination && version === generation.current) await calculate(scenario, time, version);
  }); }
  async function replay(value) {
    setAt(value); clearRoutes(); if (!scenario || !value) return;
    await run(async version => { const time = new Date(value + 'Z').toISOString(); await readScenario(scenario, time, version); if (origin && destination && version === generation.current) await calculate(scenario, time, version); });
  }
  async function feed(source) { await run(async version => {
    await api(`/ingestion/${source}`, { method: 'POST' });
    const data = await api(`/disasters?mode=${source === 'anchorage-2018' ? 'historical' : 'live'}&source=${source === 'nws' ? 'NWS' : 'USGS'}`);
    if (version === generation.current) setEvents(data.items);
  }); }

  return <div className="geo-workspace">
    <div className="geo-commandbar"><div><span className="section-kicker">STUDY AREA</span><select aria-label="Study region" value={region} onChange={e => setRegion(e.target.value)}>{regions.map(r => <option key={r.id} value={r.id}>{r.name}{r.network_ready ? '' : ' â€” data not loaded'}</option>)}</select></div><div className={`geo-readiness ${available ? '' : 'not-ready'}`}><span className="status-dot"/>{loading ? 'Loading road network' : available ? 'Road network ready' : 'Routing unavailable'}</div><button className="button primary" disabled={!demoScenario || !available || !ready || loading || working} onClick={loadDemo}><Play size={15}/>Load routing demonstration</button></div>
    {error && <div className="error-box" role="alert"><AlertCircle size={18}/>{error}</div>}
    <div className="geo-grid"><section className="geo-map-panel panel"><div className="geo-map-heading"><div><h3>{study?.name || 'Loading study areas'}</h3><span>{available ? 'Current OSM roads Â· Human-reviewed scenarios' : 'Geographic context only Â· No routing dataset'}</span></div><button className="button secondary" disabled={!available || loading} onClick={() => fit(roads.current.features.flatMap(f => f.geometry.coordinates))}><RotateCcw size={14}/>Fit region</button></div>
      <div className="geo-map-wrap"><div className="geo-map" ref={container}/>{loading && <div className="geo-map-message" role="status">Loading cached road networkâ€¦</div>}{!loading && study && !available && <div className="geo-map-message"><Layers size={26}/><h3>Road data is not loaded for this region.</h3><p>You can view the area, but scenario creation and routing are disabled. Choose Anchorage for the prepared demonstration.</p><button className="button primary" onClick={() => setRegion('anchorage')}>Open Anchorage</button></div>}{tool !== 'inspect' && <div className="geo-map-prompt"><MapPin size={16}/>{tool === 'origin' ? 'Click to place A Â· origin' : 'Click to place B Â· destination'}<button onClick={() => setTool('inspect')}>Cancel</button></div>}</div>
      <div className="geo-legend"><span><i className="legend-baseline"/>Baseline</span><span><i className="legend-adapted"/>Adapted</span><span><i className="legend-blocked"/>Blocked edge</span><label><input type="checkbox" checked={baseVisible} onChange={e => setBaseVisible(e.target.checked)}/>Basemap</label><label><input type="checkbox" checked={networkVisible} onChange={e => setNetworkVisible(e.target.checked)}/>Road overlay</label></div>{mapError && baseVisible && <p className="geo-map-warning" role="status">{mapError}</p>}
    </section>
    <aside className="geo-tools panel"><div className="section-kicker">RESPONSE SIMULATOR</div><h3>Plan. Disrupt. Compare.</h3><p className="geo-help">Create a separate scenario, place endpoints on the map, then inspect a road to test a closure.</p><label>Operating mode<select value={mode} onChange={e => setMode(e.target.value)} disabled={!!scenario || working}><option value="simulation">Damage simulation</option><option value="historical">Historical replay</option><option value="live">Live monitoring</option></select></label><div className="geo-two-actions"><button className="button primary" disabled={!available || loading || working} onClick={create}>New scenario</button><button className="button secondary" disabled={!scenario || working} onClick={() => { setScenario(null); setStates({}); setObservations([]); clearRoutes(); }}>Reset view</button></div><label>Saved scenario<select value={scenario?.id || ''} disabled={!available || loading || working} onChange={e => resume(e.target.value)}><option value="" disabled>Select a saved scenario</option>{scenarios.filter(s => s.region_id === region).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
    {scenario && <><div className="geo-scenario"><CheckCircle2 size={15}/>{scenario.mode} Â· {scenario.id.slice(0,8)}</div>{mode !== 'live' && <label>Replay time Â· UTC<input aria-label="Replay time UTC" type="datetime-local" value={at} disabled={working} onChange={e => replay(e.target.value)}/></label>}<button className={`button ${tool !== 'inspect' ? 'primary' : 'secondary'}`} disabled={working} onClick={() => setTool('origin')}><MapPin size={16}/>Place origin & destination</button><div className="geo-endpoints"><div><b>A</b><span>{origin ? origin.map(x => x.toFixed(4)).join(', ') : 'Click the map to place origin'}</span></div><div><b>B</b><span>{destination ? destination.map(x => x.toFixed(4)).join(', ') : 'Then place destination'}</span></div></div><button className="button primary" disabled={working || !origin || !destination || (mode !== 'live' && !at)} onClick={() => run(version => calculate(scenario, asOf(), version))}><Route size={16}/>{working ? 'Workingâ€¦' : 'Compare routes'}</button></>}
    {selected && <div className="geo-selected"><div className="section-kicker">SELECTED DIRECTED EDGE</div><h4>{selected.properties.name || 'Unnamed road'}</h4><code>{String(selected.id)}</code><p>Changes affect this direction only. Reverse and parallel edges remain separate.</p><div className="geo-two-actions"><button className="button primary" disabled={!scenario || working} onClick={() => changeState('blocked')}>Block edge</button><button className="button secondary" disabled={!scenario || working} onClick={() => changeState('open')}>Reopen</button></div></div>}
    <p className="geo-help">Modern road snapshot, not exact 2018 conditions. Simulation changes are labelled Simulated. Other manual observations require verification.</p></aside></div>
    {result && <section className="geo-result panel" aria-label="Route results"><div><span className="section-kicker">{result.reachable ? 'ROUTE COMPARISON' : 'NO USABLE ROUTE'}</span><h3>{result.reachable ? 'The effect of this disruption' : 'Destination is unreachable'}</h3><p>Real cached roads Â· Simulated observations Â· {stamp(result.as_of)}</p></div><div className="route-stats"><div>Baseline<strong>{result.baseline ? (result.baseline.modeled_time_s/60).toFixed(1)+' min' : 'No path'}</strong></div><div>Adapted<strong>{result.adapted ? (result.adapted.modeled_time_s/60).toFixed(1)+' min' : 'No path'}</strong></div><div>Difference<strong>{result.delay_s == null ? 'â€”' : result.delay_s.toFixed(1)+' sec'}</strong></div></div><div className="geo-result-note">{result.excluded_edges.length} excluded directed edges Â· {result.alternatives.length} candidates. Modeled speeds, not live traffic. No route is guaranteed safe.</div></section>}
    <div className="geo-evidence-grid"><section className="panel geo-evidence"><div className="geo-evidence-heading"><div><span className="section-kicker">SOURCE EVIDENCE</span><h3>Disaster events</h3></div><span className="badge">{events.length} loaded</span></div><div className="geo-feed-actions"><button disabled={working} onClick={() => feed('usgs')}>Refresh earthquakes</button><button disabled={working} onClick={() => feed('nws')}>Refresh NWS alerts</button><button disabled={working} onClick={() => feed('anchorage-2018')}>Anchorage 2018</button></div><p className="geo-help">Provider feeds can include events beyond the selected area. Refresh cooldown: 60 seconds.</p><div className="geo-evidence-scroll">{events.length ? events.slice(0,30).map(event => <article key={event.id}><span className="badge blue">{event.evidence}</span><h4>{event.title}</h4><p>{event.source} Â· {stamp(event.occurred_at)} Â· {event.verification}{event.active === false ? ' Â· Inactive' : ''}</p></article>) : <p className="geo-help">No cached events. Refresh a feed to load official source records.</p>}</div></section><section className="panel geo-evidence"><span className="section-kicker">SCENARIO AUDIT</span><h3>Observation timeline</h3><div className="geo-evidence-scroll">{observations.length ? observations.map(o => <article key={o.id}><span className="badge">{o.evidence}</span><h4>{o.state} Â· {o.asset_id}</h4><p>{stamp(o.observed_at)} Â· {o.verification}</p></article>) : <div className="geo-timeline-empty"><Layers size={28}/><p>No scenario changes yet.</p><span>Load the demonstration or record a road state to see evidence here.</span></div>}</div></section></div>
  </div>;
}
