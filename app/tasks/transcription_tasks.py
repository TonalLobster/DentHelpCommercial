"""
Celery tasks for audio transcription and summary generation.
"""
import os
import json
import logging
import tempfile
import requests
import base64
import gc  # För minneshantering
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
def process_transcription(self, file_path=None, title=None, user_id=None, temp_file=True, 
                         encoded_data=None, filename=None):
    """
    Process an audio file: process, transcribe, and generate summary.
    
    Args:
        file_path (str, optional): Path to the audio file or temp file ID
        title (str): Title for the transcription
        user_id (int): User ID of the owner
        temp_file (bool): Whether file_path is a temporary file that should be deleted
        encoded_data (str, optional): Base64-encoded audio data
        filename (str, optional): Original filename for base64 data
        
    Returns:
        dict: Result containing transcription ID and status
    """
    temp_file_path = None
    
    try:
        # Import these inside the task to avoid circular imports
        from app.services.audio_processor import process_audio
        from app.services.summary_service import generate_summary
        from app.models.transcription import Transcription
        from app import db
        
        # Hantera antingen filsökväg eller base64-data
        if encoded_data:
            logger.info(f"Starting transcription from base64 data, filename: {filename}")
            # Dekoda base64 till temporär fil
            temp_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=f".{filename.split('.')[-1]}" if filename else ".mp3").name
            with open(temp_file_path, 'wb') as f:
                f.write(base64.b64decode(encoded_data))
            
            # Frigör minne genom att rensa encoded_data
            encoded_data = None
            gc.collect()
            
            # Använd denna temporära fil
            file_path = temp_file_path
        elif file_path:
            logger.info(f"Starting transcription task for file: {file_path}")
        else:
            error_msg = "Neither file_path nor encoded_data provided"
            logger.error(error_msg)
            return {'status': 'error', 'error': error_msg}
        
        # Get OpenAI API key
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            from app.services.transcription_service import get_api_key
            api_key = get_api_key()
            
        if not api_key:
            raise ValueError("OpenAI API key not found")
        
        # Update state
        self.update_state(state='TRANSCRIBING', meta={'status': 'Transcribing audio'})
        
        # Transcribe using OpenAI API directly
        try:
            with open(file_path, 'rb') as f:
                # Optimera minnesanvändning genom att använda chunked uploads om möjligt
                transcription_response = requests.post(
                    'https://api.openai.com/v1/audio/transcriptions',
                    headers={'Authorization': f'Bearer {api_key}'},
                    files={'file': f},
                    data={'model': 'whisper-1', 'language': 'sv'}
                )
                
            if transcription_response.status_code != 200:
                raise RuntimeError(f"OpenAI API error: {transcription_response.text}")
                
            transcription_text = transcription_response.json()['text']
            logger.info(f"Transcription completed, length: {len(transcription_text)} characters")
            
            # Frigör minne
            transcription_response = None
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error during transcription: {str(e)}")
            raise
        
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
    finally:
        # Alltid rensa upp temporära filer och frig??r minne, även om ett fel inträffade
        try:
            # Ta bort temporär fil om vi skapade den från base64-data
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.info(f"Removed temporary file: {temp_file_path}")
                
            # Om det är en vanlig filsökväg och den ska tas bort
            if temp_file and file_path and file_path != temp_file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed temporary file: {file_path}")
                
            # Explicit frigör minne
            gc.collect()
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")