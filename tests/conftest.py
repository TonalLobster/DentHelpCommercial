import os
import pytest
from app import create_app, db
from app.models.user import User

@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL', 'sqlite:///:memory:'),
        'WTF_CSRF_ENABLED': False,
    })

    # Create the database and the database tables
    with app.app_context():
        db.create_all()
        
        # Create test user
        user = User(username='testuser', email='test@example.com', license_number='TEST123')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

    yield app

    # Clean up / reset resources
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()


@pytest.fixture
def auth(client):
    """Authentication helper for tests."""
    class AuthActions:
        def __init__(self, client):
            self._client = client
            
        def login(self, username='testuser', password='password'):
            return self._client.post(
                '/auth/login',
                data={'username': username, 'password': password}
            )
            
        def logout(self):
            return self._client.get('/auth/logout')
            
    return AuthActions(client)