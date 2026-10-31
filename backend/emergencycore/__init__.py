from flask import Flask
from .config import load_config
from .database import init_database
from .api.routes import register_routes
from .migrations import migrate
from .api.intelligence import intelligence

def create_app(overrides=None):
    app = Flask(__name__)
    app.config.update(load_config())
    if overrides:
        app.config.update(overrides)
        if 'DATABASE_PATH' in overrides and 'DATABASE_URL' not in overrides:
            app.config.update(DATABASE_URL='', DATABASE_URL_UNPOOLED='')
    if app.config['APP_ENV'] == 'production' and not app.config['API_TOKEN']:
        raise ValueError('Production requires API_TOKEN; configure the operator secret on the backend')
    if app.config['AI_PROVIDER'] not in {'none', 'groq', 'huggingface', 'compatible'}:
        raise ValueError('Unsupported AI_PROVIDER')
    if app.config['APP_ENV'] == 'production' and not app.config.get('DATABASE_URL'):
        raise ValueError('Production requires DATABASE_URL for PostgreSQL')
    init_database(app)
    migrate(app)
    register_routes(app)
    app.register_blueprint(intelligence, url_prefix='/api/v1')
    return app
