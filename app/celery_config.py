import os
import ssl

# Kontrollera om det är en rediss:// URL och hantera SSL-inställningar
redis_url = os.environ.get('REDIS_URL', os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))
redis_options = {}

if redis_url.startswith('rediss://'):
    redis_options = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }

# Celery configuration
broker_url = redis_url
broker_transport_options = redis_options
result_backend = redis_url
result_backend_transport_options = redis_options

# Resten av din konfiguration
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