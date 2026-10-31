"""Real OSM graph + explicitly simulated disruption linked to official earthquake."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import networkx as nx
from emergencycore import create_app
from emergencycore.services import regions, simulation, routing


def main():
    app = create_app()
    with app.app_context():
        network = regions.load_network('anchorage')
        graph = routing.graph_from(network)
        origin = max(graph.nodes, key=lambda n: graph.out_degree(n))
        distances = nx.single_source_dijkstra_path_length(graph, origin, weight='travel_time_s')
        destination = max(distances, key=distances.get)
        nodes = {n['id']: n for n in network['nodes']}
        baseline = routing.route(graph, origin, destination, nodes)
        selected = None
        for edge_id in baseline['edge_ids']:
            edge = next(e for e in network['edges'] if e['id'] == edge_id)
            candidate = graph.copy()
            candidate.remove_edge(edge['u'], edge['v'], key=edge_id)
            alternative = routing.route(candidate, origin, destination, nodes)
            if alternative and alternative['edge_ids'] != baseline['edge_ids']:
                selected = edge_id
                break
        if selected is None:
            raise RuntimeError('No reroutable single-edge disruption found on selected path')
        scenario = simulation.create({'name': 'Anchorage 2018 context — SIMULATED road disruption',
            'region_id': 'anchorage', 'mode': 'simulation', 'disaster_id': 'usgs:ak018fcnsk91'})
        request = {'origin': nodes[origin]['coordinates'], 'destination': nodes[destination]['coordinates']}
        before = routing.calculate(scenario['id'], dict(request, at='2018-11-30T17:29:29Z'))
        observation = simulation.observe(scenario['id'], {'asset_id': selected, 'state': 'blocked',
            'observed_at': '2018-11-30T18:00:00Z',
            'note': 'SIMULATION ONLY: selected OSM edge blocked to demonstrate rerouting. Not a documented 2018 closure.'})
        after = routing.calculate(scenario['id'], dict(request, at='2018-11-30T18:30:00Z'))
        assert observation['evidence'] == 'Simulated'
        assert selected not in after['adapted']['edge_ids']
        assert before['adapted']['edge_ids'] != after['adapted']['edge_ids']
        result = {'scenario_id': scenario['id'], 'request': request, 'blocked_edge': selected,
            'before_seconds': before['adapted']['modeled_time_s'], 'after_seconds': after['adapted']['modeled_time_s'],
            'delay_s': after['delay_s'], 'evidence': observation['evidence'], 'graph_version': network['version'],
            'notice': 'Official earthquake context; modern OSM graph; simulated closure. Not historical damage reconstruction.'}
        target = Path(app.config['GEO_DATA_DIR']) / 'anchorage' / 'demo-result.json'
        target.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
