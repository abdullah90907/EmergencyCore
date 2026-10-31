"""Local quantized MiniLM embeddings; similarity scores are not probabilities."""
from functools import lru_cache
from pathlib import Path
from threading import Lock

MODEL_ID = 'Xenova/all-MiniLM-L6-v2'
PROTOTYPES = {
    'fire': 'A building is burning with flames and heavy smoke. A wildfire threatens homes.',
    'flood': 'Heavy rainfall caused rising flood water. Streets and homes are submerged.',
    'earthquake': 'An earthquake shook buildings and caused structures to collapse.',
    'medical': 'A person is injured, bleeding, unconscious or needs an ambulance.',
    'storm': 'A severe storm with strong winds, lightning or a cyclone is approaching.',
    'other': 'A general report or routine information with no specific emergency described.',
}


class SemanticUnavailable(Exception):
    pass


class SemanticModel:
    def __init__(self, directory):
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer
            self.np = np
            self.tokenizer = Tokenizer.from_file(str(Path(directory) / 'tokenizer.json'))
            self.tokenizer.enable_truncation(max_length=256)
            self.tokenizer.enable_padding()
            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            self.session = ort.InferenceSession(str(Path(directory) / 'model_quantized.onnx'),
                                               sess_options=options, providers=['CPUExecutionProvider'])
            self.lock = Lock()
            self.labels = list(PROTOTYPES)
            self.prototypes = self.encode(list(PROTOTYPES.values()))
        except Exception as exc:
            raise SemanticUnavailable('Local embedding model unavailable; run the model setup script.') from exc

    def encode(self, texts):
        np = self.np
        with self.lock:
            encoded = self.tokenizer.encode_batch(texts)
        arrays = {'input_ids': np.array([e.ids for e in encoded], dtype=np.int64),
                  'attention_mask': np.array([e.attention_mask for e in encoded], dtype=np.int64),
                  'token_type_ids': np.array([e.type_ids for e in encoded], dtype=np.int64)}
        inputs = {key.name: arrays[key.name] for key in self.session.get_inputs()}
        tokens = self.session.run(None, inputs)[0]
        mask = arrays['attention_mask'][..., None]
        pooled = (tokens * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
        return pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)

    def classify(self, text):
        scores = self.encode([text])[0] @ self.prototypes.T
        ranked = sorted(zip(self.labels, scores.tolist()), key=lambda x: x[1], reverse=True)
        return {'status': 'available', 'model': MODEL_ID, 'method': 'embedding_similarity',
                'suggested_category': ranked[0][0],
                'scores': [{'category': label, 'similarity': round(score, 4)} for label, score in ranked],
                'limitations': 'Prototype similarity, not a disaster-trained classifier or confidence probability. English-focused; input truncated to 256 tokens.'}


@lru_cache(maxsize=2)
def get_model(directory):
    return SemanticModel(directory)


def classify(text, config):
    if str(config.get('LOCAL_MODEL_ENABLED', 'true')).lower() != 'true':
        return {'status': 'disabled'}
    try:
        return get_model(config['LOCAL_MODEL_DIR']).classify(text)
    except SemanticUnavailable as exc:
        return {'status': 'unavailable', 'message': str(exc), 'model': MODEL_ID}
