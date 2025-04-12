"""
Celery configuration for DentalScribe AI.
Simplified to ensure proper Redis connection with or without SSL.
"""
import os
import ssl

# Get the Redis URL from environment
redis_url = os.environ.get('REDIS_URL', os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))

# Determine if SSL should be used
use_ssl = redis_url.startswith('rediss://')

# Basic Celery configuration
broker_url = redis_url
result_backend = redis_url

# Set SSL configuration only if using SSL
if use_ssl:
    broker_use_ssl = {'ssl_cert_reqs': ssl.CERT_NONE}
    redis_backend_use_ssl = {'ssl_cert_reqs': ssl.CERT_NONE}
    broker_transport_options = {'ssl_cert_reqs': ssl.CERT_NONE}

# Task settings
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
enable_utc = True

# Beat schedule for periodic tasks
beat_schedule = {
    'cleanup_old_temp_files': {
        'task': 'app.tasks.scheduled_tasks.cleanup_old_temp_files',
        'schedule': 86400.0,  # Every 24 hours in seconds
    },
}