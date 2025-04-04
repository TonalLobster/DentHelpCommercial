"""
Application factory setup and initialization.
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Vänligen logga in för att få åtkomst till denna sida.'
login_manager.login_message_category = 'info'

def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    
    # Load default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///dentalscribe.db').replace('postgres://', 'postgresql://'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY'),
        MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100MB max upload
        VALID_LICENSES=os.environ.get('VALID_LICENSES', '').split(',')
    )
    
    # Load test config if passed
    if test_config:
        app.config.from_mapping(test_config)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # Import and register blueprints
    from app.routes.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    
    from app.routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    # Import models for migrations
    from app.models.user import User
    from app.models.transcription import Transcription
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Setup error handlers
    from app.utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    # Setup Jinja filters
    from app.utils.jinja_filters import register_filters
    register_filters(app)
    
    return app