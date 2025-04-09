"""
Celery worker configuration for DentalScribe AI.
"""
import os
from celery import Celery
from app import celery_config

# Configure Celery directly from our celery_config module
celery = Celery('dental_scribe')
celery.config_from_object(celery_config)

# Only create Flask application context when needed
class ContextTask(celery.Task):
    abstract = True
    
    def __call__(self, *args, **kwargs):
        from app import create_app
        with create_app().app_context():
            return self.run(*args, **kwargs)

celery.Task = ContextTask

# Import tasks lazily to avoid circular imports
@celery.on_after_finalize.connect
def setup_imports(sender, **kwargs):
    # Import tasks modules only when Celery is fully initialized
    import importlib
    try:
        importlib.import_module('app.tasks.transcription_tasks')
        importlib.import_module('app.tasks.scheduled_tasks')
    except ImportError as e:
        print(f"Warning: Could not import task modules: {e}")