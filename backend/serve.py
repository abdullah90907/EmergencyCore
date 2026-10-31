"""Render/local production entry point. No downloads or scheduler at startup."""
import os
from waitress import serve
from emergencycore import create_app

if __name__ == '__main__':
    serve(create_app(), host='0.0.0.0', port=int(os.getenv('PORT', '5000')), threads=8)
