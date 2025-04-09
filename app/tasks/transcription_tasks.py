"""
Celery tasks for transcription and summarization processing.
"""
import logging
import json
import tempfile
import os
import base64
import datetime
from io import BytesIO
from celery import shared_task
from flask import current_app

# Configure logging
logger = logging.getLogger(__name__)

@shared_task(bind=True, name='transcribe_audio')
def transcribe_audio_task(self, audio_data, form_data, user_id):
    """
    Process an audio file asynchronously:
    1. Process audio for optimal transcription
    2. Transcribe audio to text
    3. Generate summary
    4. Save to database
    
    Args:
        audio_data: Base64 encoded audio data or file path
        form_data: Dictionary with form data (title, etc.)
        user_id: ID of the user who submitted the transcription
        
    Returns:
        dict: Result information including transcription ID
    """
    logger.info(f"Starting async transcription process for user {user_id}")
    self.update_state(state='INITIALIZING', meta={'status': 'Starting process...'})
    
    try:
        # We need to import these here to avoid circular imports
        from app import db
        from app.models.transcription import Transcription
        from app.services.audio_processor import process_audio
        from app.services.transcription_service import transcribe_audio
        from app.services.summary_service import generate_summary
        
        # Get title from form data
        title = form_data.get('title')
        if not title or title.strip() == '':
            title = f'Transkription {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}'
        
        # Get patient ID if provided
        patient_id = form_data.get('patient_id')
            
        # Process audio data
        audio_file = None
        temp_file_path = None
        
        self.update_state(state='PROCESSING', meta={'status': 'Processing audio...'})
        logger.info("Processing audio data")
        
        # Handle different types of audio_data
        if isinstance(audio_data, str):
            if audio_data.startswith('data:'):
                # Handle base64 encoded data
                header, encoded = audio_data.split(",", 1)
                audio_bytes = base64.b64decode(encoded)
                audio_file = BytesIO(audio_bytes)
                audio_file.name = "recorded_audio.webm"
                logger.info("Decoded base64 audio data")
            elif os.path.exists(audio_data):
                # Handle file path
                logger.info(f"Reading audio from file: {audio_data}")
                temp_file_path = audio_data  # Remember to clean this up later
                with open(audio_data, 'rb') as f:
                    audio_file = BytesIO(f.read())
                    audio_file.name = os.path.basename(audio_data)
            else:
                raise ValueError(f"Invalid audio data: {audio_data[:30]}...")
        else:
            # Handle binary data directly
            audio_file = BytesIO(audio_data)
            audio_file.name = "uploaded_audio.wav"
            logger.info("Using raw binary audio data")
        
        # Process audio for better transcription
        self.update_state(state='PROCESSING', meta={'status': 'Optimizing audio...'})
        processed_audio, processing_error = process_audio(audio_file)
        
        if processing_error:
            logger.warning(f"Audio processing warning: {processing_error}")
        
        # Transcribe audio
        self.update_state(state='TRANSCRIBING', meta={'status': 'Transcribing audio...'})
        logger.info("Starting transcription")
        transcription_text = transcribe_audio(processed_audio)
        logger.info(f"Transcription completed, length: {len(transcription_text)} characters")
        
        # Generate summary
        self.update_state(state='SUMMARIZING', meta={'status': 'Generating AI summary...'})
        logger.info("Generating summary")
        summary_dict = generate_summary(transcription_text)
        logger.info("Summary generation completed")
        
        # Create and save transcription
        self.update_state(state='SAVING', meta={'status': 'Saving results...'})
        logger.info(f"Creating transcription record with title: {title}")
        
        new_transcription = Transcription(
            title=title,
            user_id=user_id,
            transcription_text=transcription_text,
            summary=json.dumps(summary_dict, ensure_ascii=False)
        )
        
        # Add patient ID if provided
        if patient_id:
            new_transcription.patient_id = patient_id
        
        # Save to database
        db.session.add(new_transcription)
        db.session.commit()
        logger.info(f"Transcription saved with ID: {new_transcription.id}")
        
        # Clean up temporary file if created
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"Removed temporary file: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Could not remove temporary file: {e}")
        
        # Return result
        return {
            'status': 'success',
            'transcription_id': new_transcription.id,
            'title': new_transcription.title
        }
        
    except Exception as e:
        logger.error(f"Error in transcription task: {str(e)}", exc_info=True)
        # Update task state with error
        self.update_state(state='FAILURE', meta={
            'status': 'error',
            'error': str(e)
        })
        # Re-raise the exception to mark the task as failed
        raise