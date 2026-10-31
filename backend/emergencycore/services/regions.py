import hashlib
import json
from pathlib import Path
from flask import current_app, g
from ..database import get_db
from .common import now
from werkzeug.exceptions import NotFound, ServiceUnavailable

REGIONS = {
    'anchorage': {'id': 'anchorage', 'name': 'Anchorage, Alaska', 'state': 'AK',
                  'center': [-149.9003, 61.2181], 'bbox': [-149.96, 61.18, -149.82, 61.24],
                  'metric_crs': 'EPSG:32606', 'historical_event_id': 'ak018fcnsk91'},
    'los-angeles': {'id': 'los-angeles', 'name': 'Los Angeles, California', 'state': 'CA',
                    'center': [-118.2437, 34.0522], 'bbox': [-118.30, 34.02, -118.20, 34.09],
                    'metric_crs': 'EPSG:32611'},
}


def registry():
    return {**REGIONS, **current_app.config.get('STUDY_REGIONS', {})}


def get_region(identifier):
    if not isinstance(identifier, str) or identifier not in registry():
        raise NotFound('Unknown region')
    return registry()[identifier]


def data_path(identifier, filename='network.json'):
    get_region(identifier)
    return Path(current_app.config['GEO_DATA_DIR']) / identifier / filename


def dataset(identifier, layer):
    get_region(identifier)
    cache = g.setdefault('_region_datasets', {})
    key = (identifier, layer)
    if key not in cache:
        row = get_db().execute('SELECT payload FROM region_datasets WHERE region_id=? AND layer=?', key).fetchone()
        path = data_path(identifier, 'network.json' if layer == 'roads' else 'assets.geojson')
        cache[key] = row['payload'].encode('utf-8') if row else path.read_bytes() if path.exists() else None
    return cache[key]


def persist_dataset(identifier, layer):
    path = data_path(identifier, 'network.json' if layer == 'roads' else 'assets.geojson')
    payload = path.read_text(encoding='utf-8')
    json.loads(payload)
    with get_db():
        get_db().execute("""INSERT INTO region_datasets(region_id,layer,payload,updated_at) VALUES(?,?,?,?)
            ON CONFLICT(region_id,layer) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at""", (identifier, layer, payload, now()))
    g.pop('_region_datasets', None)


def load_network(identifier):
    raw = dataset(identifier, 'roads')
    if raw is None:
        raise ServiceUnavailable('Road network is not prepared. Run backend/scripts/prepare_region.py.')
    network = json.loads(raw)
    network['version'] = hashlib.sha256(raw).hexdigest()[:20]
    return network


def describe(identifier):
    result = dict(get_region(identifier))
    result['network_ready'] = dataset(identifier, 'roads') is not None
    result['assets_ready'] = dataset(identifier, 'assets') is not None
    if result['network_ready']:
        graph = load_network(identifier)
        result['network'] = {k: graph.get(k) for k in ('version', 'fetched_at', 'source', 'historical_caveat')}
        result['network'].update(nodes=len(graph['nodes']), edges=len(graph['edges']))
    return result
