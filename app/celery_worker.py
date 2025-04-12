"""
Celery worker configuration för DentalScribe AI.
Skapar och konfigurerar Celery-instansen som används av applikationen.
"""
import os
from celery import Celery

def create_celery():
    """Skapa och konfigurera Celery-instans"""
    
    # Initiera Celery med konfiguration från celery_config
    celery = Celery('dental_scribe')
    celery.config_from_object('app.celery_config')
    
    # Definiera ContextTask för att skapa Flask app-kontext vid task-körning
    class ContextTask(celery.Task):
        abstract = True
        
        def __call__(self, *args, **kwargs):
            from app import create_app
            with create_app().app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

# Skapa och exportera Celery-instansen
celery = create_celery()

# Import tasks vid uppstart för att registrera dem
@celery.on_after_finalize.connect
def setup_imports(sender, **kwargs):
    # Importera tasks-moduler först när Celery är fullt initierad
    import importlib
    try:
        importlib.import_module('app.tasks.transcription_tasks')
        importlib.import_module('app.tasks.scheduled_tasks')
    except ImportError as e:
        print(f"Varning: Kunde inte importera task-moduler: {e}")

# Om filen körs direkt, starta en worker
if __name__ == '__main__':
    celery.start()