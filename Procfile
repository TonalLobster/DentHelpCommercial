web: gunicorn wsgi:app
worker: celery -A celery_config.celery worker --loglevel=info
flower: celery -A celery_config.celery flower --port=$PORT --url_prefix=flower