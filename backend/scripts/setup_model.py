"""Explicit download and real inference smoke test; no API token required."""
import json
import hashlib
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download, model_info

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from emergencycore.services.semantic import MODEL_ID, get_model

destination = ROOT / 'models' / 'minilm'
destination.mkdir(parents=True, exist_ok=True)
revision = model_info(MODEL_ID).sha
manifest = {'model': MODEL_ID, 'revision': revision, 'files': {}}
for remote, local in [('tokenizer.json', 'tokenizer.json'),
                      ('onnx/model_quantized.onnx', 'model_quantized.onnx')]:
    downloaded = hf_hub_download(MODEL_ID, remote, revision=revision, local_dir=destination / 'download')
    import shutil
    shutil.copyfile(downloaded, destination / local)
    manifest['files'][local] = hashlib.sha256((destination / local).read_bytes()).hexdigest()
(destination / 'manifest.json').write_text(json.dumps(manifest, indent=2))
model = get_model(str(destination))
examples = ['A house is burning with flames and smoke.',
            'Flood water has submerged homes after heavy rain.']
results = [model.classify(text) for text in examples]
assert [r['suggested_category'] for r in results] == ['fire', 'flood'], results
print(json.dumps({'smoke_test': 'passed', 'results': results}, indent=2))
