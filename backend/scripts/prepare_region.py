"""Download an actual current OSM driving graph and optional infrastructure layer."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from emergencycore import create_app
from emergencycore.services.regions import get_region, data_path, persist_dataset
from emergencycore.services.common import now


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('region', help='Configured study region ID, e.g. anchorage')
    parser.add_argument('--refresh-roads', action='store_true', help='Replace road snapshot; existing scenarios will require recreation')
    parser.add_argument('--overpass-url', help='Optional operator-selected Overpass API base URL')
    parser.add_argument('--assets', action='store_true', help='Also download buildings and mapped facilities')
    args = parser.parse_args()
    import osmnx as ox
    app = create_app()
    with app.app_context():
        region = get_region(args.region)
        ox.settings.cache_folder = str(Path(app.config['GEO_DATA_DIR']) / 'osm-cache')
        ox.settings.requests_timeout = 180
        ox.settings.use_cache = True
        ox.settings.http_user_agent = 'EmergencyCore-local-research/2.0'
        if args.overpass_url:
            ox.settings.overpass_url = args.overpass_url
        destination = data_path(args.region)
        if not destination.exists() or args.refresh_roads:
            graph = ox.graph_from_bbox(tuple(region['bbox']), network_type='drive')
            graph = ox.routing.add_edge_speeds(graph, fallback=30)
            graph = ox.routing.add_edge_travel_times(graph)
            nodes = [{'id': str(key), 'coordinates': [float(n['x']), float(n['y'])]} for key, n in graph.nodes(data=True)]
            edges = []
            for u, v, key, edge in graph.edges(keys=True, data=True):
                geometry = edge.get('geometry')
                edges.append({'id': f'{u}:{v}:{key}', 'u': str(u), 'v': str(v),
                              'length_m': float(edge['length']), 'travel_time_s': float(edge['travel_time']),
                              'name': str(edge.get('name', 'Unnamed road')), 'osmid': str(edge.get('osmid', '')),
                              'coordinates': list(geometry.coords) if geometry is not None else None})
            destination = data_path(args.region)
            destination.parent.mkdir(parents=True, exist_ok=True)
            result = {'nodes': nodes, 'edges': edges, 'source': 'OpenStreetMap contributors / OSMnx',
                      'attribution_url': 'https://www.openstreetmap.org/copyright', 'fetched_at': now(),
                      'bbox': region['bbox'], 'speed_assumption': 'OSM/inferred speeds; fallback 30 km/h. No live traffic.',
                      'historical_caveat': 'Modern OSM snapshot; not an exact reconstruction of the 2018 road network.'}
            temporary = destination.with_suffix('.tmp')
            temporary.write_text(json.dumps(result), encoding='utf-8')
            temporary.replace(destination)
            print(json.dumps({'region': args.region, 'nodes': len(nodes), 'edges': len(edges), 'saved_to': str(destination)}))
        else:
            print(json.dumps({'region': args.region, 'roads': 'reusing cached snapshot'}))
        persist_dataset(args.region, 'roads')
        if args.assets:
            frame = ox.features_from_bbox(tuple(region['bbox']), tags={'building': True, 'amenity': ['hospital', 'fire_station', 'police']})
            features = []
            for (kind, osmid), row in frame.iterrows():
                if row.geometry is None or row.geometry.is_empty:
                    continue
                from shapely.geometry import mapping
                props = {k: str(row[k]) for k in ('name', 'building', 'amenity') if k in row and str(row[k]) != 'nan'}
                features.append({'type': 'Feature', 'id': f'osm:{kind}:{osmid}', 'geometry': mapping(row.geometry), 'properties': props})
            target = data_path(args.region, 'assets.geojson')
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps({'type': 'FeatureCollection', 'features': features,
                'source': 'OpenStreetMap contributors', 'fetched_at': now(),
                'notice': 'Mapped facilities and buildings; operational status and completeness are unknown.'}), encoding='utf-8')
            temporary.replace(target)
            persist_dataset(args.region, 'assets')
            print(json.dumps({'assets': len(features), 'saved_to': str(target)}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'preparation_failed', 'error_type': type(exc).__name__,
            'message': 'Could not finish region preparation. Existing road/asset snapshots are preserved. Check provider availability before retrying.'}), file=sys.stderr)
        raise SystemExit(1) from None
