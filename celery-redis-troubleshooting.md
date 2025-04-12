# DentalScribe AI: Celery and Redis Troubleshooting Guide

This guide will help you diagnose and fix issues with Celery and Redis in your DentalScribe application.

## Common Issues & Solutions

### 1. Redis Connection Problems

#### Symptoms:
- `ConnectionError: Error 111 connecting to localhost:6379. Connection refused.`
- Tasks stay in "PENDING" state forever
- Celery worker crashes with connection errors

#### Solutions:

1. **Verify Redis is running:**
   ```bash
   # On Linux/macOS
   redis-cli ping
   # Should return "PONG"
   
   # Check if Redis service is running
   sudo systemctl status redis  # Linux
   brew services list           # macOS
   ```

2. **Check Redis URL configuration:**
   - Ensure `REDIS_URL` or `CELERY_BROKER_URL` is correctly set in your `.env` file
   - For local development: `redis://localhost:6379/0`
   - For Heroku: Should be automatically set by Redis add-on

3. **Test Redis connectivity directly:**
   ```bash
   # Run the provided test script
   python test_redis.py
   ```

4. **If using SSL (rediss://):**
   - Make sure SSL parameters are correctly configured
   - Heroku Redis uses SSL by default

### 2. Celery Worker Not Starting

#### Symptoms:
- `ModuleNotFoundError: No module named 'app.celery_worker'`
- `ImportError: cannot import name 'celery' from 'app.celery_worker'`
- Worker starts but immediately exits

#### Solutions:

1. **Fix circular imports:**
   - Ensure you're not importing Flask app in celery_worker.py
   - Use the revised celery_worker.py provided above

2. **Check Python path:**
   ```bash
   # Make sure you're in the project root
   pwd
   # Start worker with proper path context
   PYTHONPATH=. celery -A app.celery_worker.celery worker --loglevel=info
   ```

3. **Verify celery installation:**
   ```bash
   pip install celery redis
   ```

### 3. Tasks Not Being Processed

#### Symptoms:
- Tasks stay in "PENDING" state
- No errors, but nothing happens
- Celery worker doesn't show any logs when tasks are submitted

#### Solutions:

1. **Check queue names:**
   - Make sure tasks and workers use the same queue
   - By default, Celery uses the "celery" queue

2. **Increase log level for debugging:**
   ```bash
   celery -A app.celery_worker.celery worker --loglevel=debug
   ```

3. **Ensure tasks are properly registered:**
   - Tasks should be imported in celery_worker.py
   - Try explicitly importing specific tasks

4. **Verify task signatures:**
   - Check that tasks are being called with the correct arguments

### 4. Proper Celery Project Structure

For a Flask application like DentalScribe, your Celery configuration should follow this structure:

```
dental-scribe-ai/
├── app/
│   ├── celery_config.py   # Celery settings
│   ├── celery_worker.py   # Celery app and context
│   └── tasks/            # Task definitions
│       ├── __init__.py
│       ├── transcription_tasks.py
│       └── scheduled_tasks.py
└── wsgi.py               # Flask application entry point
```

## Command Reference

### Local Development

1. **Start Redis (if not running as a service):**
   ```bash
   redis-server
   ```

2. **Start Celery worker:**
   ```bash
   celery -A app.celery_worker.celery worker --loglevel=info
   ```

3. **Start Celery beat (for scheduled tasks):**
   ```bash
   celery -A app.celery_worker.celery beat --loglevel=info
   ```

4. **Monitor tasks with Flower (optional):**
   ```bash
   pip install flower
   celery -A app.celery_worker.celery flower --port=5555
   # Then open http://localhost:5555 in your browser
   ```

### Heroku Deployment

1. **Add Redis add-on:**
   ```bash
   heroku addons:create heroku-redis:mini
   ```

2. **Configure dynos in Procfile:**
   ```
   web: gunicorn wsgi:app
   worker: celery -A app.celery_worker.celery worker --loglevel=info
   beat: celery -A app.celery_worker.celery beat --loglevel=info
   ```

3. **Scale worker dynos:**
   ```bash
   heroku ps:scale web=1 worker=1 beat=1
   ```

4. **View logs:**
   ```bash
   heroku logs --tail
   ```

## Testing Celery Integration

To verify your Celery setup is working correctly, run this test:

1. Open a Python shell in your project context:
   ```bash
   flask shell
   ```

2. Try submitting a test task:
   ```python
   from app.tasks.transcription_tasks import process_transcription
   
   # Create a mock task (adjust parameters as needed)
   result = process_transcription.delay('/path/to/test/file.wav', 'Test Transcription', 1, False)
   
   # Check task ID
   print(f"Task ID: {result.id}")
   
   # Check task status
   print(f"Task status: {result.status}")
   ```

3. Monitor the worker logs to see if the task is being processed

## Additional Resources

- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/documentation)
- [Heroku Redis Add-on](https://devcenter.heroku.com/articles/heroku-redis)
