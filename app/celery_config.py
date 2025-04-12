"""
Konfigurationsfil för Celery.
Hanterar anslutningar till Redis med stöd för både lokal utveckling och Heroku-deployment.
"""
import os
import ssl
import platform

# Windows-specifika inställningar
if platform.system() == 'Windows':
    # Använd threads på Windows istället för processer
    worker_pool = 'solo'  # Använd en enda process
    worker_concurrency = 1  # Bara 1 worker
else:
    # På Unix-liknande system
    worker_pool = 'prefork'
    worker_concurrency = 4  # Eller antal CPU-kärnor

# Hämta Redis URL från miljövariabler
redis_url = os.environ.get('REDIS_URL', os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))

# Basala Celery-konfigurationer
broker_url = redis_url
result_backend = redis_url
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
enable_utc = True

# Använd SSL-konfiguration endast om vi använder en säker Redis-anslutning (rediss://)
if redis_url.startswith('rediss://'):
    # SSL-konfigurationer för broker
    broker_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    
    # SSL-konfigurationer för result backend
    redis_backend_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    
    # Transportalternativ (används av kombu/celery)
    broker_transport_options = {
        'ssl_cert_reqs': ssl.CERT_NONE,
    }

# Beat schedule för periodiska uppgifter (om du använder celery beat)
beat_schedule = {
    'cleanup_old_temp_files': {
        'task': 'app.tasks.cleanup_old_temp_files',
        'schedule': 86400.0,  # Varje 24 timmar i sekunder
    },
}

# Debug-loggning vid utveckling
if os.environ.get('FLASK_ENV') == 'development':
    worker_log_level = 'DEBUG'
    task_log_level = 'DEBUG'
else:
    worker_log_level = 'INFO'
    task_log_level = 'INFO'