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
    
    # Configure app
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'default-dev-key'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'postgresql://localhost/dental_scribe'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY')
    )
    
    # Fix Heroku PostgreSQL URL (they use 'postgres://' instead of 'postgresql://')
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
    
    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    CORS(app)
    
    # Only enable HTTPS in production
    if os.environ.get('FLASK_ENV') == 'production':
        Talisman(app, content_security_policy=None)
    
    # Register blueprints - FIXED: use the correct blueprint names as defined in the route files
    from app.routes.auth import auth
    app.register_blueprint(auth)
    
    from app.routes.main import main
    app.register_blueprint(main)
    
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