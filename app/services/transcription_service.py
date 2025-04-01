import openai
from flask import current_app
import tempfile
import os

def transcribe_audio_file(audio_file):
    """
    Transcribe audio using OpenAI Whisper API
    
    Args:
        audio_file: The uploaded file object
        
    Returns:
        str: The transcribed text
    """
    try:
        openai.api_key = current_app.config['OPENAI_API_KEY']
        
        # Save the uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
            tmp.write(audio_file.read())
            tmp_name = tmp.name
        
        with open(tmp_name, 'rb') as audio:
            transcription = openai.Audio.transcribe(
                model="whisper-1",
                file=audio,
                language="sv"
            )
        
        # Remove temp file
        os.unlink(tmp_name)
        return transcription.text
        
    except Exception as e:
        current_app.logger.error(f"Transcription error: {str(e)}")
        raise