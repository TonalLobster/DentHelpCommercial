## Background Processing with Celery

DentalScribe AI använder Celery för att köra tunga processer som transkribering och sammanfattning i bakgrunden. Detta förbättrar användarupplevelsen genom att göra applikationen mer responsiv.

### Lokalt utvecklingssetup för Celery

1. Installera Redis (används som message broker och result backend):

   **Ubuntu/Debian:**
   ```bash
   sudo apt-get install redis-server
   ```

   **macOS:**
   ```bash
   brew install redis
   ```

   **Windows:**
   Ladda ner Redis för Windows eller använd WSL.

2. Starta Redis:
   ```bash
   redis-server
   ```

3. Starta Celery worker:
   ```bash
   python dev.py worker
   ```

4. (Valfritt) För schemalagda uppgifter, starta Celery beat:
   ```bash
   python dev.py beat
   ```

5. (Valfritt) För övervakning, starta Flower:
   ```bash
   # Installera först flower: pip install flower
   python dev.py flower
   ```
   Öppna sedan http://localhost:5555 i din webbläsare för att se Celery-övervakningen.

### Skapa nya bakgrundsuppgifter

1. Lägg till nya tasks i `app/tasks/`:
   ```python
   from app.celery_worker import celery

   @celery.task(bind=True, name='app.tasks.my_new_task')
   def my_new_task(self, arg1, arg2):
       # Task code here
       return result
   ```

2. Anropa task från din route eller annan kod:
   ```python
   from app.tasks.my_module import my_new_task
   
   # Anropa asynkront (returnerar direkt)
   task = my_new_task.delay(arg1, arg2)
   
   # Hämta task_id för statusuppdateringar
   task_id = task.id
   ```

### Heroku-deployment med Celery

Se till att aktivera både en web-dyno och en worker-dyno:

```bash
heroku ps:scale web=1 worker=1
```

För schemalagda uppgifter behöver du också aktivera en beat-dyno:

```bash
heroku ps:scale beat=1
```

Mer information finns i [heroku-migration-guide.md](./heroku-migration-guide.md).