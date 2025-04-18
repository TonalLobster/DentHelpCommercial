import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
csrf = CSRFProtect()

def create_app():
    # Create and configure the app
    app = Flask(__name__)
    
    # Get the database URL
    database_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/dental_scribe')
    
    # Ensure the URL uses postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Add SSL parameters to force a secure connection for production
    if os.environ.get('FLASK_ENV') == 'production':
        if '?' not in database_url:
            database_url += '?sslmode=require'
        elif 'sslmode' not in database_url:
            database_url += '&sslmode=require'
    
    # Configure app
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'default-dev-key'),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY'),
        VALID_LICENSES=os.environ.get('VALID_LICENSES', '').split(','),
        
        # Celery configuration
        CELERY_BROKER_URL=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        CELERY_RESULT_BACKEND=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
        CELERY_TASK_SERIALIZER='json',
        CELERY_ACCEPT_CONTENT=['json'],
        CELERY_RESULT_SERIALIZER='json',
        CELERY_ENABLE_UTC=True,
    )
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
    
    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    CORS(app)
    
    # Only enable HTTPS in production
    if os.environ.get('FLASK_ENV') == 'production':
        Talisman(app, content_security_policy=None)

    # Registrera SSE blueprint
    from app.routes.sse import sse as sse_blueprint
    app.register_blueprint(sse_blueprint, url_prefix='/sse')
    
    # Import and register blueprints
    from app.routes.auth import auth
    app.register_blueprint(auth, url_prefix='/auth')
    
    from app.routes.main import main
    app.register_blueprint(main, url_prefix='')
    
    # Ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Register custom Jinja2 filters
    from app.utils.jinja_filters import register_filters
    register_filters(app)
    
    # Register CLI commands
    from app.cli import register_commands
    register_commands(app)
    
    # Register error handlers
    from app.utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    return app

# Add user loader function
from app.models.user import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))