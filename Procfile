web: gunicorn wsgi:app
worker: celery -A app.celery_worker.celery worker --loglevel=info
