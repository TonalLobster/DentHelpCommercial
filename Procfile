web: gunicorn wsgi:app
worker: celery -A app.celery_worker.celery worker --loglevel=info
scheduler: celery -A app.celery_worker.celery beat --loglevel=info