"""
Scheduled tasks using Celery beat.
"""
from app.celery_worker import celery
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@celery.task(name='app.tasks.cleanup_old_temp_files')
def cleanup_old_temp_files():
    """
    Cleanup temporary files that might have been left behind.
    This task is scheduled to run periodically via Celery beat.
    """
    import os
    import tempfile
    from datetime import datetime, timedelta

    logger.info("Running temporary file cleanup...")
    
    # Get the temp directory
    temp_dir = tempfile.gettempdir()
    
    # Define how old files should be before deletion (e.g., 24 hours)
    max_age = timedelta(hours=24)
    
    # Get current time
    now = datetime.now()
    
    # Get all files in the temp directory
    file_count = 0
    error_count = 0
    
    try:
        for root, dirs, files in os.walk(temp_dir):
            for filename in files:
                # Check if it's likely one of our temp files (can be customized)
                if filename.endswith(('.wav', '.mp3', '.m4a', '.ogg')):
                    file_path = os.path.join(root, filename)
                    
                    try:
                        # Get file stats
                        stats = os.stat(file_path)
                        
                        # Get file creation/modification time
                        last_modified = datetime.fromtimestamp(stats.st_mtime)
                        
                        # If file is older than max_age, delete it
                        if now - last_modified > max_age:
                            os.remove(file_path)
                            file_count += 1
                    except (FileNotFoundError, PermissionError) as e:
                        logger.warning(f"Could not process file {file_path}: {str(e)}")
                        error_count += 1
                        continue
        
        logger.info(f"Cleanup complete. Removed {file_count} temporary files. Errors: {error_count}")
        return {
            'cleaned_files': file_count, 
            'errors': error_count,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error during temp file cleanup: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

# Set up periodic tasks
@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Set up periodic tasks with Celery beat.
    This function runs when Celery is initialized.
    """
    # Run the cleanup task every day at midnight
    sender.add_periodic_task(
        # crontab(hour=0, minute=0),  # More flexible scheduling option
        86400.0,  # Every 24 hours in seconds
        cleanup_old_temp_files.s(),
        name='cleanup_old_temp_files'
    )
    
    # You can add more scheduled tasks here as needed