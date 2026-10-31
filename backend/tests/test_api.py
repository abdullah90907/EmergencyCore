import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from PIL import Image
from backend.emergencycore import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        Path('instance').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir='instance')
        self.config = {'TESTING': True, 'DATABASE_PATH': str(Path(self.temp.name) / 'test.db'),
                       'AI_PROVIDER': 'none', 'API_TOKEN': '', 'LOCAL_MODEL_ENABLED': 'false'}
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def create(self, **kwargs):
        return self.client.post('/api/v1/incidents', json={
            'description': 'Flood water rising; two people trapped.', 'urgency': 'low', **kwargs})

    def test_lifecycle_persistence_and_dashboard(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        item = response.json
        self.assertEqual(item['analysis']['priority'], 'critical')
        self.assertEqual(item['analysis']['ai']['status'], 'disabled')
        url = '/api/v1/incidents/' + item['id']
        self.assertEqual(self.client.patch(url, json={'status': 'resolved'}).status_code, 409)
        for status in ['verified', 'responding', 'resolved']:
            self.assertEqual(self.client.patch(url, json={'status': status}).json['status'], status)
        self.assertEqual(self.client.get('/api/v1/dashboard').json['active'], 0)
        other = create_app(self.config).test_client()
        self.assertEqual(other.get(url).json['status'], 'resolved')
        self.assertEqual(other.get('/api/v1/incidents?status=resolved').json['total'], 1)

    def test_validation(self):
        for data in [None, [], {'description': 'short'}, {'description': 'a valid description', 'latitude': 100},
                     {'description': 'a valid description', 'latitude': 20},
                     {'description': 'a valid description', 'latitude': {}, 'longitude': 20}]:
            response = self.client.post('/api/v1/incidents', json=data)
            self.assertIn(response.status_code, [400, 415])
        self.assertEqual(self.client.get('/api/v1/incidents?limit=no').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/incidents/missing').status_code, 404)

    def test_analysis_and_model_readiness(self):
        response = self.client.post('/api/v1/analyze', json={'description': 'Smoke and flames in a building'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['category'], 'fire')
        self.assertEqual(response.json['semantic']['status'], 'disabled')
        self.assertEqual(self.client.get('/api/v1/incidents').json['total'], 0)
        self.assertEqual(self.client.get('/api/v1/models/status').json['local_model']['status'], 'disabled')
        item = self.create().json
        self.assertEqual(self.client.get('/api/v1/incidents/' + item['id'] + '/related').status_code, 503)

    def test_auth_and_cors(self):
        self.app.config['API_TOKEN'] = 'test-token'
        self.assertEqual(self.client.get('/api/v1/incidents').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/health').status_code, 200)
        response = self.client.get('/api/v1/incidents', headers={
            'Authorization': 'Bearer test-token', 'Origin': 'http://localhost:5173'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'http://localhost:5173')

    def test_event_replay(self):
        item = self.create().json
        self.client.patch('/api/v1/incidents/' + item['id'], json={'status': 'verified'})
        response = self.client.get('/api/v1/events', headers={'Last-Event-ID': '1'}, buffered=False)
        iterator = iter(response.response)
        next(iterator)
        event = next(iterator).decode()
        self.assertIn('incident.updated', event)
        self.assertIn('id: 2', event)
        response.close()

    @patch('backend.emergencycore.services.analysis.requests.post')
    def test_ai_enrichment_and_failure(self, post):
        self.app.config.update(AI_PROVIDER='huggingface', AI_MODEL='test-model', AI_API_KEY='secret')
        post.return_value = Mock(json=lambda: {'choices': [{'message': {'content': 'Coordinator advisory'}}]})
        self.assertEqual(self.create().json['analysis']['ai']['advisory'], 'Coordinator advisory')
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer secret')
        post.side_effect = requests.Timeout()
        result = self.create()
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json['analysis']['ai']['status'], 'unavailable')

    @patch('backend.emergencycore.api.routes.requests.get')
    def test_weather_success_and_failure(self, get):
        get.return_value = Mock(json=lambda: {'current': {'temperature_2m': 30}, 'hourly': {}})
        url = '/api/v1/weather?latitude=24.86&longitude=67.01'
        self.assertEqual(self.client.get(url).json['source'], 'Open-Meteo')
        get.side_effect = requests.Timeout()
        self.assertEqual(self.client.get(url).status_code, 502)
        self.assertEqual(self.client.get('/api/v1/weather?latitude=nan&longitude=0').status_code, 400)

    @patch('backend.emergencycore.services.analysis.requests.post')
    def test_vision(self, post):
        self.assertEqual(self.client.post('/api/v1/damage-assessments').status_code, 503)
        self.app.config.update(AI_PROVIDER='compatible', AI_VISION_MODEL='vision-test')
        post.return_value = Mock(json=lambda: {'choices': [{'message': {'content': 'Visible debris; expert review required.'}}]})
        image = io.BytesIO()
        Image.new('RGB', (32, 32)).save(image, format='PNG')
        image.seek(0)
        response = self.client.post('/api/v1/damage-assessments', data={'image': (image, 'test.png')})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['needs_human_review'])
        bad = self.client.post('/api/v1/damage-assessments', data={'image': (io.BytesIO(b'bad'), 'bad.png')})
        self.assertEqual(bad.status_code, 400)


if __name__ == '__main__':
    unittest.main()

