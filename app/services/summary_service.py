"""
Transcription service for converting audio to text using OpenAI's Whisper API.
"""
import os
import logging
import tempfile
from io import BytesIO
import openai
from flask import current_app

logger = logging.getLogger(__name__)

def get_api_key():
    """Get OpenAI API key from environment or application config."""
    if api_key := os.environ.get("OPENAI_API_KEY"):
        return api_key
    
    if hasattr(current_app, 'config') and current_app.config.get('OPENAI_API_KEY'):
        return current_app.config['OPENAI_API_KEY']
    
    return None

def transcribe_audio(audio_file):
    """
    Transcribe an audio file using OpenAI's Whisper API.
    
    Args:
        audio_file: A BytesIO object or file-like object with audio data
        
    Returns:
        str: Transcribed text
    """
    try:
        # Try to get API key
        api_key = get_api_key()
            
        if not api_key:
            raise ValueError("OpenAI API key missing. Check environment variables or app configuration.")
        
        # Create client with API key
        client = openai.OpenAI(api_key=api_key)
        
        # Handle different types of input
        temp_file = None
        try:
            if hasattr(audio_file, 'read'):
                # Reset read head to beginning of file if it's a file-like object
                audio_file.seek(0)
                
                # If it's a file-like object that isn't BytesIO, save it temporarily
                if not isinstance(audio_file, BytesIO):
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    temp_file.write(audio_file.read())
                    temp_file.close()
                    audio_file.seek(0)  # Reset read head again
                    
                    # Open the temporary file
                    with open(temp_file.name, 'rb') as f:
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                            language="sv"  # Swedish
                        )
                else:
                    # If it's a BytesIO, use it directly
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="sv"  # Swedish
                    )
            else:
                # If it's not a file-like object, assume it's a path
                with open(audio_file, 'rb') as f:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="sv"  # Swedish
                    )
                    
            return transcription.text
            
        finally:
            # Remove temporary file if created
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
                
    except Exception as e:
        # Log the actual error for debugging
        logger.error(f"Transcription error: {str(e)}")
        raise RuntimeError(f"Error during transcription: {str(e)}")