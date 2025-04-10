import os
import ssl

# Basal URL utan modifieringar för loggning
base_redis_url = os.environ.get('REDIS_URL', os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))

# Skapa en korrekt formaterad URL för Redis med SSL-parametrar
if base_redis_url.startswith('rediss://'):
    # Dela URL för att hantera parametrar korrekt
    if '?' in base_redis_url:
        uri, params = base_redis_url.split('?', 1)
        param_dict = dict(p.split('=') for p in params.split('&') if '=' in p)
        # Lägg till SSL-parametern om den inte finns
        if 'ssl_cert_reqs' not in param_dict:
            param_dict['ssl_cert_reqs'] = 'CERT_NONE'
        # Återskapa URL med parametrar
        redis_url = f"{uri}?{'&'.join(f'{k}={v}' for k, v in param_dict.items())}"
    else:
        # Ingen parameter finns, lägg till ssl_cert_reqs
        redis_url = f"{base_redis_url}?ssl_cert_reqs=CERT_NONE"
else:
    # Inte en säker anslutning, använd ursprunglig URL
    redis_url = base_redis_url

# Celery configuration
broker_url = redis_url
result_backend = redis_url

# SSL-konfigurationer för både broker och backend
broker_use_ssl = {
    'ssl_cert_reqs': ssl.CERT_NONE
}

redis_backend_use_ssl = {
    'ssl_cert_reqs': ssl.CERT_NONE
}

# Transportalternativ (används av kombu/celery)
broker_transport_options = {
    'ssl_cert_reqs': ssl.CERT_NONE,
}

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