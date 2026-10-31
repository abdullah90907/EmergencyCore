import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from backend.emergencycore import create_app
from backend.emergencycore.database import get_db
from backend.emergencycore.services import disasters


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='backend')
        self.root = Path(self.temp.name).resolve()
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': str(self.root / 'test.sqlite3'),
            'GEO_DATA_DIR': str(self.root), 'LOCAL_MODEL_ENABLED': 'false', 'AI_PROVIDER': 'none', 'API_TOKEN': ''})
        self.client = self.app.test_client()
        target = self.root / 'anchorage'; target.mkdir()
        self.nodes = [{'id': 'a', 'coordinates': [-149.9, 61.218]}, {'id': 'b', 'coordinates': [-149.89, 61.218]},
                      {'id': 'c', 'coordinates': [-149.89, 61.228]}, {'id': 'd', 'coordinates': [-149.88, 61.218]}]
        edge = lambda key, u, v, seconds: dict(id=key, u=u, v=v, travel_time_s=seconds, length_m=seconds * 10)
        self.graph = {'nodes': self.nodes, 'edges': [edge('ab', 'a', 'b', 10), edge('ab-slow', 'a', 'b', 20),
            edge('bd', 'b', 'd', 10), edge('ac', 'a', 'c', 20), edge('cd', 'c', 'd', 20)],
            'source': 'Simulated test fixture', 'fetched_at': '2026-01-01T00:00:00+00:00'}
        (target / 'network.json').write_text(json.dumps(self.graph))
        (target / 'assets.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': [{
            'id': 'hospital', 'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [-149.88, 61.218]},
            'properties': {'amenity': 'hospital', 'evidence': 'Simulated'}}]}))

    def tearDown(self):
        self.temp.cleanup()

    def create(self, mode='simulation'):
        response = self.client.post('/api/v1/scenarios', json={'region_id': 'anchorage', 'name': 'Test', 'mode': mode})
        self.assertEqual(response.status_code, 201)
        return response.json['id']

    def observe(self, identifier, edge, state='blocked', **extra):
        response = self.client.post(f'/api/v1/scenarios/{identifier}/observations', json={
            'asset_id': edge, 'state': state, 'note': 'Test evidence', **extra})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def route(self, identifier, **extra):
        response = self.client.post(f'/api/v1/scenarios/{identifier}/routes', json={
            'origin': self.nodes[0]['coordinates'], 'destination': self.nodes[-1]['coordinates'], **extra})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def test_parallel_edges_and_scenario_isolation(self):
        first, second = self.create(), self.create()
        self.assertEqual(self.route(first)['adapted']['edge_ids'], ['ab', 'bd'])
        observation = self.observe(first, 'ab', evidence='Official', reviewed=True)
        self.assertEqual(observation['evidence'], 'Simulated')
        self.assertEqual(observation['verification'], 'unverified')
        rerouted = self.route(first)
        self.assertEqual(rerouted['adapted']['edge_ids'], ['ab-slow', 'bd'])
        self.assertEqual(rerouted['delay_s'], 10)
        self.assertEqual(self.route(second)['adapted']['edge_ids'], ['ab', 'bd'])
        self.observe(first, 'ab-slow')
        self.assertEqual(self.route(first)['adapted']['edge_ids'], ['ac', 'cd'])
        self.observe(first, 'ac')
        self.assertFalse(self.route(first)['reachable'])

    def test_direction_and_unavailable_facility(self):
        identifier = self.create()
        reverse = self.route(identifier, origin=self.nodes[-1]['coordinates'], destination=self.nodes[0]['coordinates'])
        self.assertIsNone(reverse['baseline'])
        self.assertFalse(reverse['reachable'])
        self.observe(identifier, 'hospital', 'unavailable')
        result = self.route(identifier, destination_asset_id='hospital')
        self.assertFalse(result['reachable'])
        self.assertEqual(result['destination_state'], 'unavailable')
        self.assertIsNotNone(result['baseline'])

    def test_historical_replay_and_reopening(self):
        identifier = self.create('historical')
        self.observe(identifier, 'ab', observed_at='2018-11-30T18:00:00Z')
        self.observe(identifier, 'ab', 'open', observed_at='2018-11-30T19:00:00Z')
        self.assertEqual(self.route(identifier, at='2018-11-30T17:00:00Z')['adapted']['edge_ids'], ['ab', 'bd'])
        self.assertEqual(self.route(identifier, at='2018-11-30T18:30:00Z')['adapted']['edge_ids'], ['ab-slow', 'bd'])
        self.assertEqual(self.route(identifier, at='2018-11-30T20:00:00Z')['adapted']['edge_ids'], ['ab', 'bd'])

    def test_graph_version_conflict_and_validation(self):
        identifier = self.create()
        response = self.client.post(f'/api/v1/scenarios/{identifier}/routes', json={'origin': [0, 0], 'destination': [0, 0]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post(f'/api/v1/scenarios/{identifier}/observations', json={'asset_id': 'fake', 'state': 'blocked', 'note': 'test'}).status_code, 404)
        self.graph['source'] = 'changed'
        (self.root / 'anchorage' / 'network.json').write_text(json.dumps(self.graph))
        self.assertEqual(self.client.get(f'/api/v1/scenarios/{identifier}').status_code, 409)

    def test_layers_matching_and_exposure(self):
        self.assertEqual(len(self.client.get('/api/v1/regions/anchorage/layers/roads').json['features']), 5)
        self.assertEqual(self.client.get('/api/v1/regions/anchorage/layers/roads?bbox=nan,0,1,1').status_code, 400)
        match = self.client.post('/api/v1/regions/anchorage/match-road', json={'coordinates': [-149.895, 61.218]})
        self.assertEqual(match.status_code, 200)
        self.assertEqual(match.json['verification'], 'unverified')
        result = self.client.post('/api/v1/regions/anchorage/exposure', json={'hazard_geometry': {
            'type': 'Polygon', 'coordinates': [[[-149.9,61.21],[-149.87,61.21],[-149.87,61.23],[-149.9,61.23],[-149.9,61.21]]]}})
        self.assertEqual(len(result.json['items']), 1)
        self.assertIn('not damage', result.json['notice'])

    @patch('backend.emergencycore.services.disasters.requests.get')
    def test_usgs_idempotency_products_and_outage(self, get):
        feature = {'id': 'test-usgs', 'geometry': {'type': 'Point', 'coordinates': [-149.95, 61.34, 46]},
            'properties': {'title': 'Test earthquake', 'time': 1543598969000, 'updated': 1543598970000,
                           'mag': 7.1, 'status': 'reviewed', 'url': 'https://earthquake.usgs.gov/',
                           'products': {'shakemap': [{'source': 'us', 'contents': {'download/grid.xml': {'url': 'https://earthquake.usgs.gov/grid.xml'}}}]}}}
        get.return_value = Mock(json=lambda: feature)
        with self.app.app_context():
            disasters.ingest_usgs(True); disasters.ingest_usgs(True)
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM disasters').fetchone()[0], 1)
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM events WHERE type='disaster.updated'").fetchone()[0], 1)
        detail = self.client.get('/api/v1/disasters/usgs:test-usgs').json
        self.assertEqual(detail['payload']['magnitude'], 7.1)
        self.assertEqual(len(detail['payload']['products']['shakemap']), 1)
        import requests
        get.side_effect = requests.Timeout()
        self.assertEqual(self.client.post('/api/v1/ingestion/usgs').status_code, 502)
        self.assertEqual(len(self.client.get('/api/v1/disasters?mode=historical').json['items']), 1)
        self.assertEqual(self.client.post('/api/v1/ingestion/usgs').status_code, 429)

    @patch('backend.emergencycore.services.disasters.requests.get')
    def test_nws_expired_and_alaska_key(self, get):
        get.return_value = Mock(json=lambda: {'features': [{'id': 'https://api.weather.gov/alerts/test', 'geometry': None,
            'properties': {'event': 'Test', 'sent': '2020-01-01T00:00:00Z', 'expires': '2020-01-02T00:00:00Z', 'status': 'Actual'}}]})
        self.assertEqual(self.client.post('/api/v1/ingestion/nws').status_code, 200)
        self.assertFalse(self.client.get('/api/v1/disasters?source=NWS').json['items'][0]['active'])
        self.app.config['ALASKA_511_API_KEY'] = ''
        self.assertEqual(self.client.post('/api/v1/ingestion/alaska511').status_code, 503)

    def test_auth_covers_new_endpoints(self):
        self.app.config['API_TOKEN'] = 'private'
        self.assertEqual(self.client.get('/api/v1/regions').status_code, 401)
        self.assertEqual(self.client.post('/api/v1/ingestion/usgs').status_code, 401)

    @patch('backend.emergencycore.services.disasters.requests.get')
    def test_successful_nws_snapshot_retires_absent_alerts(self, get):
        get.return_value = Mock(json=lambda: {'features': [{'id': 'https://api.weather.gov/alerts/retire-test', 'geometry': None,
            'properties': {'event': 'Flood Warning', 'sent': '2026-01-01T00:00:00Z',
                           'expires': '2099-01-01T00:00:00Z', 'status': 'Actual', 'messageType': 'Alert'}}]})
        with self.app.app_context():
            disasters.ingest_nws('test')
        self.assertTrue(self.client.get('/api/v1/disasters?source=NWS').json['items'][0]['active'])
        get.return_value = Mock(json=lambda: {'features': []})
        with self.app.app_context():
            disasters.ingest_nws('test')
        self.assertFalse(self.client.get('/api/v1/disasters?source=NWS').json['items'][0]['active'])

    def test_evidence_batch_rolls_back_on_invalid_mapping(self):
        from backend.emergencycore.services.simulation import observe
        from werkzeug.exceptions import NotFound
        identifier = self.create('historical')
        with self.app.app_context():
            with self.assertRaises(NotFound):
                with get_db():
                    observe(identifier, {'asset_id': 'ab', 'state': 'blocked', 'note': 'Original source reviewed',
                        'observed_at': '2018-11-30T18:00:00Z', 'source_url': 'https://dot.alaska.gov/example', 'reviewed': True}, trusted=True, commit=False)
                    observe(identifier, {'asset_id': 'bad-mapping', 'state': 'blocked', 'note': 'Invalid'}, trusted=True, commit=False)
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM observations').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
