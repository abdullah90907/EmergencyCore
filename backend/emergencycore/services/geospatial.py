import json
from pyproj import Transformer
from shapely.geometry import LineString, Point, mapping, shape
from shapely import transform as transform_geometry
from werkzeug.exceptions import NotFound
from .regions import data_path, get_region, load_network, dataset
from .common import point


def transform(project, geometry):
    return transform_geometry(geometry, project, interleaved=False)


def metric_transform(region_id):
    return Transformer.from_crs('EPSG:4326', get_region(region_id)['metric_crs'], always_xy=True).transform


def edge_shape(edge, nodes):
    return LineString(edge.get('coordinates') or [nodes[edge['u']]['coordinates'], nodes[edge['v']]['coordinates']])


def assets(region_id):
    raw = dataset(region_id, 'assets')
    if raw is None:
        return {'type': 'FeatureCollection', 'features': [], 'notice': 'Asset layer not downloaded'}
    return json.loads(raw)


def nearest_edge(region_id, coordinates, max_distance=100):
    network = load_network(region_id)
    nodes = {n['id']: n for n in network['nodes']}
    project = metric_transform(region_id)
    location = transform(project, Point(point(coordinates)))
    candidate = min(((transform(project, edge_shape(e, nodes)).distance(location), e) for e in network['edges']), key=lambda x: x[0], default=None)
    if candidate is None or candidate[0] > max_distance:
        raise NotFound('No road edge within the matching tolerance')
    distance, edge = candidate
    return {'edge_id': edge['id'], 'distance_m': round(distance, 2), 'graph_version': network['version'],
            'verification': 'unverified', 'notice': 'Nearest-edge candidate only. Check road name, direction and segment extent before applying a closure.'}


def roads(region_id, bbox=None):
    network = load_network(region_id)
    nodes = {n['id']: n for n in network['nodes']}
    features = []
    for edge in network['edges']:
        geom = edge_shape(edge, nodes)
        if bbox and not geom.intersects(bbox):
            continue
        features.append({'type': 'Feature', 'id': edge['id'], 'geometry': mapping(geom),
                         'properties': {k: v for k, v in edge.items() if k != 'coordinates'}})
    return {'type': 'FeatureCollection', 'features': features, 'graph_version': network['version'],
            'source': network['source'], 'fetched_at': network['fetched_at']}
