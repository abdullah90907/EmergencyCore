import json
from flask import Blueprint, current_app, jsonify, request
from shapely.geometry import box
from werkzeug.exceptions import BadRequest, BadGateway, TooManyRequests
from ..database import get_db
from ..services import disasters, regions, simulation, routing, impact, traffic, decision
from ..services.common import now, number, point, utc
from ..services.geospatial import assets, roads, nearest_edge

intelligence = Blueprint('intelligence', __name__)


def body():
    data = request.get_json()
    if not isinstance(data, dict):
        raise BadRequest('Expected a JSON object')
    return data


def ingest_source(source):
    sources = {'usgs': lambda: disasters.ingest_usgs(), 'anchorage-2018': lambda: disasters.ingest_usgs(True),
               'nws': lambda: disasters.ingest_nws(current_app.config['NWS_USER_AGENT']),
               'alaska511': lambda: traffic.ingest(current_app.config['ALASKA_511_API_KEY'])}
    if source not in sources:
        raise BadRequest('Unknown source')
    row = get_db().execute('SELECT attempted_at FROM ingestion_status WHERE source=?', (source,)).fetchone()
    if row:
        from datetime import datetime
        if (datetime.fromisoformat(now()) - datetime.fromisoformat(row['attempted_at'])).total_seconds() < 60:
            raise TooManyRequests('Wait at least 60 seconds between ingestion attempts for this source')
    try:
        return disasters.tracked(source, sources[source])
    except (KeyError, TypeError, ValueError, IndexError):
        raise BadGateway('Provider returned an unsupported data schema; cached data retained') from None


@intelligence.get('/regions')
def region_list():
    return jsonify(items=[regions.describe(key) for key in regions.registry()])


@intelligence.get('/regions/<identifier>')
def region_details(identifier):
    return jsonify(regions.describe(identifier))


@intelligence.get('/regions/<identifier>/layers/<layer>')
def layer(identifier, layer):
    regions.get_region(identifier)
    if layer == 'assets':
        return jsonify(assets(identifier))
    if layer != 'roads':
        raise BadRequest('layer must be roads or assets')
    bounds = request.args.get('bbox')
    bbox = None
    if bounds:
        try:
            west, south, east, north = [float(v) for v in bounds.split(',')]
        except ValueError:
            raise BadRequest('bbox must be west,south,east,north') from None
        point([west, south]); point([east, north])
        if west >= east or south >= north:
            raise BadRequest('Invalid bbox ordering')
        bbox = box(west, south, east, north)
    return jsonify(roads(identifier, bbox))


@intelligence.post('/regions/<identifier>/match-road')
def match(identifier):
    data = body()
    return jsonify(nearest_edge(identifier, data.get('coordinates'), number(data.get('max_distance_m', 100), 1, 500)))


@intelligence.post('/regions/<identifier>/exposure')
def exposure(identifier):
    regions.get_region(identifier)
    return jsonify(impact.exposure(identifier, body().get('hazard_geometry')))


@intelligence.post('/ingestion/<source>')
def ingestion(source):
    return jsonify(source=source, imported=ingest_source(source))


@intelligence.get('/ingestion/status')
def ingestion_status():
    return jsonify(items=[dict(r) for r in get_db().execute('SELECT * FROM ingestion_status')])


@intelligence.get('/disasters')
def disaster_list():
    mode = request.args.get('mode', 'live')
    if mode not in ('live', 'historical'):
        raise BadRequest('mode must be live or historical')
    limit = int(number(request.args.get('limit', 100), 1, 1000))
    offset = int(number(request.args.get('offset', 0), 0, 1000000))
    source = request.args.get('source')
    where, params = 'mode=?', [mode]
    if source:
        where += ' AND source=?'; params.append(source)
    rows = get_db().execute('SELECT * FROM disasters WHERE ' + where + ' ORDER BY occurred_at DESC LIMIT ? OFFSET ?', params + [limit, offset])
    items = []
    for row in rows:
        item = dict(row); item['payload'] = json.loads(item['payload'])
        if item['source'] == 'NWS':
            expires = item['payload'].get('expires')
            item['active'] = bool(expires and utc(expires) > now() and item['payload'].get('in_active_feed') and item['payload'].get('status') == 'Actual' and item['payload'].get('message_type') != 'Cancel')
        items.append(item)
    return jsonify(items=items, limit=limit, offset=offset,
                   notice='USGS feed is global M2.5+ in the past day; filter by geometry for your US study area. Cached NWS alerts retain expiry and active flags. Check ingestion freshness.')


@intelligence.get('/disasters/<path:identifier>')
def disaster_details(identifier):
    from werkzeug.exceptions import NotFound
    row = get_db().execute('SELECT * FROM disasters WHERE id=?', (identifier,)).fetchone()
    if row is None:
        raise NotFound('Disaster event not found')
    item = dict(row); item['payload'] = json.loads(item['payload'])
    return jsonify(item)


@intelligence.route('/scenarios', methods=['GET', 'POST'])
def scenarios():
    if request.method == 'POST':
        return jsonify(simulation.create(body())), 201
    return jsonify(items=[dict(r) for r in get_db().execute('SELECT * FROM scenarios ORDER BY created_at DESC LIMIT 200')])


@intelligence.get('/scenarios/<identifier>')
def scenario_details(identifier):
    item, _ = simulation.scenario(identifier)
    latest, cutoff = simulation.states(identifier, request.args.get('at'))
    return jsonify(**item, as_of=cutoff, asset_states=latest)


@intelligence.route('/scenarios/<identifier>/observations', methods=['GET', 'POST'])
def observations(identifier):
    simulation.scenario(identifier)
    if request.method == 'POST':
        return jsonify(simulation.observe(identifier, body())), 201
    return jsonify(items=[dict(r) for r in get_db().execute('SELECT * FROM observations WHERE scenario_id=? ORDER BY observed_at,recorded_at,id', (identifier,))])


@intelligence.post('/scenarios/<identifier>/routes')
def routes(identifier):
    return jsonify(routing.calculate(identifier, body())), 201


@intelligence.get('/scenarios/<identifier>/routes')
def route_history(identifier):
    simulation.scenario(identifier)
    return jsonify(items=[json.loads(r['payload']) for r in get_db().execute('SELECT payload FROM route_results WHERE scenario_id=? ORDER BY created_at DESC LIMIT 50', (identifier,))])


@intelligence.get('/scenarios/<identifier>/decision')
def decisions(identifier):
    return jsonify(decision.explain(identifier, request.args.get('at')))


@intelligence.get('/regions/<identifier>/traffic')
def traffic_data(identifier):
    regions.get_region(identifier)
    return jsonify(items=traffic.candidates(identifier))
