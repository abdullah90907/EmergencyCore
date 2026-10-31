from pathlib import Path
import tempfile
import unittest
from backend.emergencycore import create_app


class DeploymentTests(unittest.TestCase):
    def test_production_requires_operator_secret(self):
        with self.assertRaisesRegex(ValueError, 'API_TOKEN'):
            create_app({'APP_ENV': 'production', 'API_TOKEN': ''})

    def test_persistent_path_restart_and_cross_origin_preflight(self):
        with tempfile.TemporaryDirectory(dir='backend') as directory:
            config = {'DATABASE_PATH': str(Path(directory).resolve() / 'persistent' / 'app.sqlite3'),
                'APP_ENV': 'development', 'API_TOKEN': 'test-secret', 'LOCAL_MODEL_ENABLED': 'false',
                'AI_PROVIDER': 'none', 'CORS_ORIGIN': 'https://example.vercel.app'}
            client = create_app(config).test_client()
            self.assertEqual(client.get('/api/v1/health').status_code, 200)
            self.assertEqual(client.get('/api/v1/incidents').status_code, 401)
            headers = {'Authorization': 'Bearer test-secret', 'Origin': config['CORS_ORIGIN']}
            saved = client.post('/api/v1/incidents', json={'description': 'Deployment persistence test report'}, headers=headers)
            self.assertEqual(saved.status_code, 201)
            self.assertEqual(saved.headers['Access-Control-Allow-Origin'], config['CORS_ORIGIN'])
            restarted = create_app(config).test_client()
            self.assertEqual(restarted.get('/api/v1/incidents', headers=headers).json['total'], 1)
            preflight = restarted.options('/api/v1/incidents', headers={'Origin': config['CORS_ORIGIN'], 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Authorization, Content-Type'})
            self.assertEqual(preflight.headers['Access-Control-Allow-Origin'], config['CORS_ORIGIN'])
            denied = restarted.get('/api/v1/incidents', headers={'Authorization': 'Bearer test-secret', 'Origin': 'https://other.vercel.app'})
            self.assertNotIn('Access-Control-Allow-Origin', denied.headers)
