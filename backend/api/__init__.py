from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def create_app(config=None):
    app = Flask(__name__)
    config = config or {}
    if config.get('SQLALCHEMY_DATABASE_URI'):
        conn_str = config['SQLALCHEMY_DATABASE_URI']
    else:
        from settings import SUPA_USER, SUPA_PASSWORD, HOST, DATABASE
        conn_str = f"postgresql://{SUPA_USER}:{SUPA_PASSWORD}@{HOST}:5432/{DATABASE}"
    app.json.sort_keys = False
    app.config['SQLALCHEMY_DATABASE_URI'] = conn_str
    app.config.update({key: value for key, value in os.environ.items() if key.startswith('VAULT_')})
    app.config.update(config)
    db.init_app(app)
    if str(app.config.get('VAULT_ENABLED', '')).lower() in {'true', '1', 'yes'}:
        from backend.filing_vault import init_app
        init_app(app)
    return app
