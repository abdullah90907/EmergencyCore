import hashlib
import json
from pathlib import Path
from flask import current_app
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


def load_network(identifier):
    path = data_path(identifier)
    if not path.exists():
        raise ServiceUnavailable('Road network is not prepared. Run backend/scripts/prepare_region.py.')
    raw = path.read_bytes()
    network = json.loads(raw)
    network['version'] = hashlib.sha256(raw).hexdigest()[:20]
    return network


def describe(identifier):
    result = dict(get_region(identifier))
    result['network_ready'] = data_path(identifier).exists()
    result['assets_ready'] = data_path(identifier, 'assets.geojson').exists()
    if result['network_ready']:
        graph = load_network(identifier)
        result['network'] = {k: graph.get(k) for k in ('version', 'fetched_at', 'source', 'historical_caveat')}
        result['network'].update(nodes=len(graph['nodes']), edges=len(graph['edges']))
    return result
