"""
Celery tasks for audio transcription and summary generation.
"""
import os
import json
import logging
import tempfile
from datetime import datetime
from io import BytesIO

# Import celery instance
try:
    from app.celery_worker import celery
except ImportError:
    # Fallback for testing or direct imports
    from celery import Celery
    celery = Celery('dental_scribe')

logger = logging.getLogger(__name__)

@celery.task(bind=True, name='app.tasks.process_transcription')
def process_transcription(self, file_path, title, user_id, temp_file=True):
    """
    Process an audio file: process, transcribe, and generate summary.
    
    Args:
        file_path (str): Path to the audio file or temp file ID
        title (str): Title for the transcription
        user_id (int): User ID of the owner
        temp_file (bool): Whether file_path is a temporary file that should be deleted
        
    Returns:
        dict: Result containing transcription ID and status
    """
    try:
        # Import these inside the task to avoid circular imports
        from app.services.audio_processor import process_audio
        from app.services.transcription_service import transcribe_audio
        from app.services.summary_service import generate_summary
        from app.models.transcription import Transcription
        from app import db
        
        logger.info(f"Starting transcription task for file: {file_path}")
        
        # Open the file for processing
        if temp_file:
            with open(file_path, 'rb') as f:
                audio_data = BytesIO(f.read())
                audio_data.name = os.path.basename(file_path)
        else:
            audio_data = file_path
            
        # Process the audio file for optimal transcription
        logger.info("Processing audio file...")
        self.update_state(state='PROCESSING_AUDIO', meta={'status': 'Processing audio'})
        processed_audio, processing_error = process_audio(audio_data)
        
        if processing_error:
            logger.warning(f"Audio processing warning: {processing_error}")
            # Continue anyway, but log the warning
        
        # Transcribe the audio
        logger.info("Transcribing audio...")
        self.update_state(state='TRANSCRIBING', meta={'status': 'Transcribing audio'})
        transcription_text = transcribe_audio(processed_audio)
        logger.info(f"Transcription completed, length: {len(transcription_text)} characters")
        
        # Generate summary
        logger.info("Generating summary...")
        self.update_state(state='GENERATING_SUMMARY', meta={'status': 'Generating summary'})
        summary_dict = generate_summary(transcription_text)
        logger.info("Summary generated")
        
        # Create title if not provided
        if not title or title.strip() == '':
            title = 'Transcription ' + datetime.now().strftime('%Y-%m-%d %H:%M')
            
        # Create new transcription record
        logger.info(f"Creating transcription record with title: {title}")
        self.update_state(state='SAVING', meta={'status': 'Saving transcription'})
        
        new_transcription = Transcription(
            title=title,
            user_id=user_id,
            transcription_text=transcription_text,
            summary=json.dumps(summary_dict, ensure_ascii=False)
        )
        
        # Save to database
        db.session.add(new_transcription)
        db.session.commit()
        logger.info(f"Transcription saved with ID: {new_transcription.id}")
        
        # Clean up temp file if needed
        if temp_file and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Removed temporary file: {file_path}")
        
        return {
            'transcription_id': new_transcription.id,
            'status': 'completed',
            'title': title
        }
        
    except Exception as e:
        logger.error(f"Error in transcription task: {str(e)}", exc_info=True)
        # Return error information
        return {
            'status': 'error',
            'error': str(e)
        }