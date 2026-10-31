import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def load_config():
    load_dotenv(BACKEND_ROOT / '.env')
    config = {key: os.getenv(key, default) for key, default in {
        'DATABASE_PATH': str(BACKEND_ROOT / 'instance' / 'emergencycore.sqlite3'),
        'AI_PROVIDER': 'none', 'AI_BASE_URL': 'https://router.huggingface.co/v1',
        'AI_MODEL': '', 'AI_VISION_MODEL': '', 'AI_API_KEY': '', 'API_TOKEN': '',
        'CORS_ORIGIN': 'http://localhost:5173',
        'LOCAL_MODEL_DIR': str(BACKEND_ROOT / 'models' / 'minilm'),
        'LOCAL_MODEL_ENABLED': 'true'}.items()}
    config.update({key: os.getenv(key, default) for key, default in {
        'GEO_DATA_DIR': str(BACKEND_ROOT / 'data'),
        'ALASKA_511_API_KEY': '',
        'NWS_USER_AGENT': 'EmergencyCore-local-prototype',
        'INGEST_INTERVAL_SECONDS': '300'}.items()})
    config.update({key: os.getenv(key, default) for key, default in {
        'GROQ_API_KEY': '', 'GROQ_MODEL': 'qwen/qwen3.8-27b',
        'GROQ_VISION_MODEL': 'qwen/qwen3.8-27b', 'GEMINI_API_KEY': '',
        'GEMINI_MODEL': 'gemini-3.8-flash', 'GEMINI_VISION_MODEL': 'gemini-3.8-flash',
        'AI_FALLBACK_ENABLED': 'true', 'AI_MAX_OUTPUT_TOKENS': '4096'}.items()})
    region_file = os.getenv('REGIONS_FILE')
    if region_file:
        location = Path(region_file)
        custom = json.loads((location if location.is_absolute() else BACKEND_ROOT / location).read_text(encoding='utf-8'))
        if not isinstance(custom, dict):
            raise ValueError('REGIONS_FILE must contain an object keyed by region ID')
        from .services.common import point
        from pyproj import CRS
        for key, region in custom.items():
            if not re.fullmatch(r'[a-z0-9-]{1,60}', key):
                raise ValueError('Region IDs must be lowercase slugs')
            point(region['center'])
            west, south, east, north = region['bbox']
            point([west, south]); point([east, north])
            if not west < east or not south < north:
                raise ValueError('Invalid region bbox')
            if not CRS.from_user_input(region['metric_crs']).is_projected:
                raise ValueError('Region metric_crs must be projected')
            region['id'] = key
        config['STUDY_REGIONS'] = custom
    path = Path(config['DATABASE_PATH'])
    config['DATABASE_PATH'] = str(path if path.is_absolute() else BACKEND_ROOT / path)
    geo_path = Path(config['GEO_DATA_DIR'])
    config['GEO_DATA_DIR'] = str(geo_path if geo_path.is_absolute() else BACKEND_ROOT / geo_path)
    config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024
    return config
