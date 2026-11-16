import pytest
from app import create_app
from app.config import Config
from app.extensions import db

@pytest.fixture
def app():
    # Use the app with current database configuration
    app = create_app(Config)
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
    })
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()
