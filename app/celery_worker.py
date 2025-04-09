"""
Celery worker configuration for DentHelp AI.
"""
import os
from celery import Celery

def create_celery(app=None):
    """
    Create a new Celery object and configure it with the Flask app.
    """
    if app is None:
        from app import create_app
        app = create_app()
    
    # Configure Celery
    celery = Celery(
        app.import_name,
        broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    )
    
    # Update Celery configuration with Flask app config
    celery.conf.update(app.config)
    
    # Add beat schedule if defined in app config
    if 'CELERYBEAT_SCHEDULE' in app.config:
        celery.conf.beat_schedule = app.config['CELERYBEAT_SCHEDULE']
    
    # Create TaskBase subclass to properly handle Flask app context
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    # Use ContextTask for all tasks
    celery.Task = ContextTask
    
    return celery

# Create the Celery instance
flask_app = None  # Will be lazily loaded when needed
celery = create_celery(flask_app)

# Import tasks to ensure they're registered with Celery
# Use late import to avoid circular imports
@celery.on_after_configure.connect
def setup_imports(sender, **kwargs):
    import app.tasks.transcription_tasks
    import app.tasks.scheduled_tasks