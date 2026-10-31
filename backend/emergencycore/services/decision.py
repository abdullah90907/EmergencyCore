"""Deterministic recommendations linked to stored evidence, not generated facts."""
from .simulation import scenario, states


def explain(identifier, at=None):
    item, graph = scenario(identifier)
    latest, cutoff = states(identifier, at)
    blocked = [v for v in latest.values() if v['state'] in ('blocked', 'unavailable')]
    return {'scenario_id': identifier, 'mode': item['mode'], 'as_of': cutoff,
            'graph_version': graph['version'], 'observed_asset_count': len(latest),
            'restricted_assets': blocked,
            'recommendations': [
                {'action': 'Review closure evidence before operational use.', 'observation_ids': [v['id'] for v in blocked]},
                {'action': 'Recalculate candidate routes after any state change.', 'observation_ids': [v['id'] for v in latest.values()]},
            ], 'notice': 'Facilities without observations have unknown operational status. Reachability alone does not establish that a destination is open or safe.'}
