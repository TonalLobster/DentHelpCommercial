"""
Celery worker configuration for DentalScribe AI.
Fixed to avoid circular imports and properly load tasks.
"""
from celery import Celery

# Create Celery instance without Flask context initially
celery = Celery('dental_scribe')
celery.config_from_object('app.celery_config')

# Define Flask context task base class
class FlaskTask(celery.Task):
    """Task that runs within Flask application context"""
    abstract = True
    
    def __call__(self, *args, **kwargs):
        # Import at runtime to avoid circular imports
        from app import create_app
        with create_app().app_context():
            return self.run(*args, **kwargs)

# Apply the Flask task class to all tasks
celery.Task = FlaskTask

# Explicitly register task modules
@celery.on_after_finalize.connect
def setup_tasks(sender, **kwargs):
    # Import task modules here to avoid circular imports
    from app.tasks import transcription_tasks, scheduled_tasks