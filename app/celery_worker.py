"""
Celery worker configuration for DentalScribe AI.
"""
import os
import ssl
from celery import Celery

# Initiera Celery med konfiguration från celery_config
celery = Celery('dental_scribe')
celery.config_from_object('app.celery_config')

# Extra SSL-konfiguration som appliceras direkt
celery.conf.update(
    broker_use_ssl={'ssl_cert_reqs': ssl.CERT_NONE},
    redis_backend_use_ssl={'ssl_cert_reqs': ssl.CERT_NONE},
    broker_transport_options={'ssl_cert_reqs': ssl.CERT_NONE}
)

# Endast skapa Flask-applikationskontext vid behov
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