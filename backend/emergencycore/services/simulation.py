import json
import uuid
from contextlib import nullcontext
from werkzeug.exceptions import BadRequest, Conflict, NotFound
from ..database import get_db
from .common import now, text, utc
from .regions import load_network
from .geospatial import assets


def scenario(identifier):
    row = get_db().execute('SELECT * FROM scenarios WHERE id=?', (identifier,)).fetchone()
    if row is None:
        raise NotFound('Scenario not found')
    result = dict(row)
    graph = load_network(result['region_id'])
    if graph['version'] != result['graph_version']:
        raise Conflict('Region graph has changed. Create a new scenario to avoid mismatched road IDs.')
    return result, graph


def emit(kind, payload):
    get_db().execute('INSERT INTO events(type,payload,created_at) VALUES(?,?,?)', (kind, json.dumps(payload), now()))


def create(data):
    mode = data.get('mode', 'simulation')
    if mode not in ('simulation', 'historical', 'live'):
        raise BadRequest('mode must be live, historical or simulation')
    region = text(data.get('region_id'), 100)
    graph = load_network(region)
    disaster_id = data.get('disaster_id')
    if disaster_id is not None:
        disaster_id = text(disaster_id, 500)
        if not get_db().execute('SELECT 1 FROM disasters WHERE id=?', (disaster_id,)).fetchone():
            raise NotFound('Disaster event not imported')
    item = dict(id=str(uuid.uuid4()), name=text(data.get('name'), 200), region_id=region,
                mode=mode, disaster_id=disaster_id, graph_version=graph['version'], created_at=now())
    with get_db():
        get_db().execute('INSERT INTO scenarios VALUES(:id,:name,:region_id,:mode,:disaster_id,:graph_version,:created_at)', item)
        emit('scenario.created', item)
    return item


def observe(identifier, data, trusted=False, commit=True):
    item, graph = scenario(identifier)
    asset_id = text(data.get('asset_id'), 200)
    valid = {e['id'] for e in graph['edges']} | {str(f['id']) for f in assets(item['region_id'])['features']}
    if asset_id not in valid:
        raise NotFound('Asset or edge not found in the pinned region dataset')
    state = data.get('state')
    if state not in ('open', 'blocked', 'damaged', 'unavailable'):
        raise BadRequest('state must be open, blocked, damaged or unavailable')
    evidence = 'Simulated' if item['mode'] == 'simulation' else 'Community-Reported'
    verification = 'unverified'
    if trusted:
        evidence = data.get('evidence', 'Official')
        if evidence not in ('Official', 'Community-Reported', 'AI-Estimated', 'Simulated'):
            raise BadRequest('Invalid evidence label')
        verification = 'reviewed' if data.get('reviewed') is True else 'unverified'
    url = data.get('source_url')
    if url is not None and (not isinstance(url, str) or len(url) > 2000 or not url.startswith('https://')):
        raise BadRequest('source_url must be an HTTPS evidence reference')
    if evidence == 'Official' and not url:
        raise BadRequest('Official observations require an evidence source URL')
    if item['mode'] == 'historical' and not data.get('observed_at'):
        raise BadRequest('Historical observations require observed_at')
    observation = dict(id=str(uuid.uuid4()), scenario_id=identifier, asset_id=asset_id,
        state=state, evidence=evidence, verification=verification,
        observed_at=utc(data['observed_at']) if data.get('observed_at') else now(),
        recorded_at=now(), source_url=url, note=text(data.get('note'), 2000))
    with get_db() if commit else nullcontext():
        get_db().execute('INSERT INTO observations VALUES(:id,:scenario_id,:asset_id,:state,:evidence,:verification,:observed_at,:recorded_at,:source_url,:note)', observation)
        emit('scenario.observation', observation)
    return observation


def states(identifier, at=None):
    cutoff = utc(at) if at else now()
    rows = get_db().execute('''SELECT * FROM observations WHERE scenario_id=? AND observed_at<=?
        ORDER BY observed_at,recorded_at,id''', (identifier, cutoff)).fetchall()
    latest = {r['asset_id']: dict(r) for r in rows}
    return latest, cutoff
