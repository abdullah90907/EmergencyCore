"""Directed multigraph routing preserving parallel edges and explicit edge IDs."""
import json
import uuid
import networkx as nx
from shapely.geometry import Point
from werkzeug.exceptions import BadRequest
from ..database import get_db
from .common import now, point
from .simulation import scenario, states
from .geospatial import metric_transform, edge_shape, assets, transform


def graph_from(network):
    graph = nx.MultiDiGraph()
    for node in network['nodes']:
        graph.add_node(node['id'], **node)
    for edge in network['edges']:
        graph.add_edge(edge['u'], edge['v'], key=edge['id'], **edge)
    return graph


def route(graph, origin, destination, nodes):
    try:
        path = nx.shortest_path(graph, origin, destination, weight='travel_time_s')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    segments = [min(graph[u][v].values(), key=lambda e: e['travel_time_s']) for u, v in zip(path, path[1:])]
    return {'node_ids': path, 'edge_ids': [e['id'] for e in segments],
            'distance_m': round(sum(e['length_m'] for e in segments), 2),
            'modeled_time_s': round(sum(e['travel_time_s'] for e in segments), 2),
            'geometry': {'type': 'MultiLineString', 'coordinates': [list(edge_shape(e, nodes).coords) for e in segments]}}


def calculate(identifier, data):
    item, network = scenario(identifier)
    latest, cutoff = states(identifier, data.get('at'))
    nodes = {n['id']: n for n in network['nodes']}
    graph = graph_from(network)
    destination_asset = data.get('destination_asset_id')
    if destination_asset is not None:
        feature = next((f for f in assets(item['region_id'])['features'] if str(f['id']) == destination_asset), None)
        if feature is None:
            raise BadRequest('Destination asset not found')
        from shapely.geometry import shape
        center = shape(feature['geometry']).representative_point()
        data = dict(data, destination=[center.x, center.y])
    project = metric_transform(item['region_id'])
    snapped = {}
    for label in ('origin', 'destination'):
        location = transform(project, Point(point(data.get(label))))
        distance, node_id = min((transform(project, Point(n['coordinates'])).distance(location), key) for key, n in nodes.items())
        if distance > 1000:
            raise BadRequest('Endpoint is more than 1000 m from the cached road network')
        snapped[label] = {'node_id': node_id, 'distance_m': round(distance, 2)}
    origin, destination = snapped['origin']['node_id'], snapped['destination']['node_id']
    baseline = route(graph, origin, destination, nodes)
    removed = []
    for u, v, key in list(graph.edges(keys=True)):
        if key in latest and latest[key]['state'] in ('blocked', 'unavailable'):
            graph.remove_edge(u, v, key)
            removed.append(latest[key])
    adapted = route(graph, origin, destination, nodes)
    facility_state = latest.get(destination_asset, {}).get('state', 'unknown')
    if destination_asset and facility_state in ('blocked', 'unavailable'):
        adapted = None
    alternatives = []
    if adapted:
        simple = nx.DiGraph()
        simple.add_nodes_from(graph.nodes())
        for u, v, edge in graph.edges(data=True):
            if not simple.has_edge(u, v) or edge['travel_time_s'] < simple[u][v]['travel_time_s']:
                simple.add_edge(u, v, travel_time_s=edge['travel_time_s'])
        from itertools import islice
        for path in islice(nx.shortest_simple_paths(simple, origin, destination, weight='travel_time_s'), 3):
            path_graph = graph.edge_subgraph([(u, v, min(graph[u][v], key=lambda k: graph[u][v][k]['travel_time_s'])) for u, v in zip(path, path[1:])]).copy()
            path_graph.add_nodes_from([origin, destination])
            alternatives.append(route(path_graph, origin, destination, nodes))
    result = dict(id=str(uuid.uuid4()), scenario_id=identifier, created_at=now(), as_of=cutoff,
        graph_version=network['version'], baseline=baseline, adapted=adapted, excluded_edges=removed,
        endpoint_snapping=snapped, reachable=adapted is not None,
        alternatives=alternatives, destination_asset_id=destination_asset, destination_state=facility_state,
        delay_s=round(adapted['modeled_time_s'] - baseline['modeled_time_s'], 2) if adapted and baseline else None,
        evidence_policy='Exclude latest blocked/unavailable observations regardless of evidence; preserve provenance for operator review.',
        limitations=['Candidate route, not a guaranteed safe evacuation path.',
                    'Times are modeled from road speed assumptions, not live traffic.',
                    'Closures apply to explicitly selected directed edges; reverse/parallel edges require their own observations.',
                    'No turn-restriction, vehicle-clearance or emergency-vehicle access model.',
                    network.get('historical_caveat', 'Current road data cannot reproduce 2018 conditions exactly.')])
    with get_db():
        get_db().execute('INSERT INTO route_results VALUES(?,?,?,?)', (result['id'], identifier, result['created_at'], json.dumps(result)))
        get_db().execute('INSERT INTO events(type,payload,created_at) VALUES(?,?,?)', ('route.created',
            json.dumps({'id': result['id'], 'scenario_id': identifier, 'reachable': result['reachable'], 'delay_s': result['delay_s']}), result['created_at']))
    return result
