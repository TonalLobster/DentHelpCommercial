"""
Separate Celery configuration to avoid circular imports.
"""
import os

# Celery configuration
broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
enable_utc = True

# Beat schedule for periodic tasks
beat_schedule = {
    'cleanup_old_temp_files': {
        'task': 'app.tasks.cleanup_old_temp_files',
        'schedule': 86400.0,  # Every 24 hours in seconds
    },
}