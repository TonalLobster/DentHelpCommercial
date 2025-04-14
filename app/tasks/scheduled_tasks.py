"""
Scheduled tasks using Celery beat.
"""
import logging
import os
import tempfile
from datetime import datetime, timedelta

# Import celery instance
try:
    from app.celery_worker import celery
except ImportError:
    # Fallback for testing or direct imports
    from celery import Celery
    celery = Celery('dental_scribe')

logger = logging.getLogger(__name__)

@celery.task(name='app.tasks.cleanup_old_temp_files')
def cleanup_old_temp_files():
    """
    En mer aggressiv rensning av temporära filer och celery-statusar
    """
    # Nuvarande filrensningskod, men gör den mer omfattande
    temp_dir = tempfile.gettempdir()
    max_age = timedelta(hours=1)  # Ändra till kortare tid för mer aggressiv rensning
    now = datetime.now()
    
    # Rensa ALLA temporära filer äldre än max_age för att fånga upp alla former av temporära filer
    for root, dirs, files in os.walk(temp_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                stats = os.stat(file_path)
                last_modified = datetime.fromtimestamp(stats.st_mtime)
                if now - last_modified > max_age:
                    os.remove(file_path)
                    logger.info(f"Removed old temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Could not process file {file_path}: {str(e)}")
    
    # Rensa Redis-uppgifter
    try:
        from celery.result import AsyncResult
        from app import db
        from app.models.transcription import Transcription
        
        # Hämta alla slutförda transkriptioner från databasen
        transcriptions = Transcription.query.all()
        
        # Ta bort uppgifts-ID från Redis
        for transcription in transcriptions:
            # Om du lagrar task_id någonstans i transcription-modellen
            # Så kan du rensa motsvarande uppgifter från Redis
            pass
            
    except Exception as e:
        logger.error(f"Error during Redis cleanup: {str(e)}")

# Set up periodic tasks
@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Set up periodic tasks with Celery beat.
    This function runs when Celery is initialized.
    """
    # Run the cleanup task every day at midnight
    sender.add_periodic_task(
        86400.0,  # Every 24 hours in seconds
        cleanup_old_temp_files.s(),
        name='cleanup_old_temp_files'
    )