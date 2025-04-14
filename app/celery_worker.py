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


celery.conf.update(
    worker_max_tasks_per_child=50,  # Starta om worker efter 50 uppgifter
    broker_connection_timeout=10,    # Timeout för broker-anslutningar
    task_time_limit=600,             # 10 minuter maximal exekveringstid
    task_soft_time_limit=540,        # 9 minuter varning innan avslut
    result_expires=3600              # Spara resultat i 1 timme sen rensa
)