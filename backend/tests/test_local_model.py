"""Runs against real downloaded weights; skipped on machines without model assets."""
import tempfile
import unittest
from pathlib import Path
from backend.emergencycore import create_app
from backend.emergencycore.config import BACKEND_ROOT
from backend.emergencycore.services.semantic import get_model

MODEL_DIR = BACKEND_ROOT / 'models' / 'minilm'


@unittest.skipUnless((MODEL_DIR / 'model_quantized.onnx').exists(), 'Run setup_model.py first')
class LocalModelTests(unittest.TestCase):
    def test_real_inference_and_semantic_search(self):
        model = get_model(str(MODEL_DIR))
        self.assertEqual(model.classify('A house is burning with flames and smoke.')['suggested_category'], 'fire')
        self.assertEqual(model.classify('Water submerged homes after a river overflowed.')['suggested_category'], 'flood')
        with tempfile.TemporaryDirectory(dir=BACKEND_ROOT) as temp:
            app = create_app({'TESTING': True, 'DATABASE_PATH': str(Path(temp) / 'test.db'),
                              'LOCAL_MODEL_ENABLED': 'true', 'API_TOKEN': '', 'AI_PROVIDER': 'none'})
            client = app.test_client()
            def report(text):
                response = client.post('/api/v1/incidents', json={'description': text})
                self.assertEqual(response.status_code, 201)
                return response.json
            first = report('Flames and smoke are coming from a burning house.')
            second = report('A residential building is on fire, with thick smoke.')
            report('Flood water has submerged roads after heavy rainfall.')
            self.assertEqual(first['analysis']['semantic']['status'], 'available')
            related = client.get('/api/v1/incidents/' + first['id'] + '/related')
            self.assertEqual(related.status_code, 200)
            self.assertEqual(related.json['items'][0]['incident']['id'], second['id'])
            self.assertEqual(client.get('/api/v1/models/status').json['local_model']['status'], 'available')
