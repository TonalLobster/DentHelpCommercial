"""
Transcription service for converting audio to text using OpenAI's Whisper API.
"""
import os
import logging
import tempfile
from io import BytesIO
import openai
from flask import current_app

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("transcription_service")

def get_api_key():
    """Get OpenAI API key from environment or application config."""
    # Prioritet: 1. Miljövariabel, 2. App-config
    if api_key := os.environ.get("OPENAI_API_KEY"):
        logger.info("Använder API-nyckel från miljövariabel")
        return api_key
    
    if hasattr(current_app, 'config') and (api_key := current_app.config.get('OPENAI_API_KEY')):
        logger.info("Använder API-nyckel från app-konfiguration")
        return api_key
    
    logger.warning("Ingen API-nyckel hittades")
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
            error_msg = "OpenAI API key missing. Check environment variables or app configuration."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Create client with API key
        try:
            client = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI klient skapad")
        except Exception as e:
            logger.error(f"Kunde inte skapa OpenAI-klient: {str(e)}")
            raise RuntimeError(f"Kunde inte skapa OpenAI-klient: {str(e)}")
        
        # Handle different types of input
        temp_file = None
        try:
            logger.info(f"Processerar ljudfil av typ: {type(audio_file).__name__}")
            
            if hasattr(audio_file, 'read'):
                # Reset read head to beginning of file if it's a file-like object
                audio_file.seek(0)
                logger.info("Återställde filpekaren till början")
                
                # If it's a file-like object that isn't BytesIO, save it temporarily
                if not isinstance(audio_file, BytesIO):
                    logger.info("Sparar fil temporärt (inte BytesIO)")
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    temp_file.write(audio_file.read())
                    temp_file.close()
                    audio_file.seek(0)  # Reset read head again
                    logger.info(f"Temporär fil skapad: {temp_file.name} ({os.path.getsize(temp_file.name)} bytes)")
                    
                    # Open the temporary file
                    with open(temp_file.name, 'rb') as f:
                        logger.info("Skickar transkriptionsbegäran till OpenAI (från temp-fil)")
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                            language="sv"  # Swedish
                        )
                else:
                    # If it's a BytesIO, use it directly
                    logger.info("Skickar transkriptionsbegäran till OpenAI (direkt BytesIO)")
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="sv"  # Swedish
                    )
            else:
                # If it's not a file-like object, assume it's a path
                logger.info(f"Använder filsökväg: {audio_file}")
                with open(audio_file, 'rb') as f:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="sv"  # Swedish
                    )
            
            logger.info("Transkription från OpenAI mottagen framgångsrikt")
            return transcription.text
            
        finally:
            # Remove temporary file if created
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
                logger.info(f"Temporär fil borttagen: {temp_file.name}")
                
    except openai.RateLimitError as e:
        logger.error(f"OpenAI API rate limit exceeded: {str(e)}")
        raise RuntimeError(f"API-gränsen för OpenAI överskriden: {str(e)}")
        
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise RuntimeError(f"OpenAI API-fel: {str(e)}")
        
    except openai.APIConnectionError as e:
        logger.error(f"OpenAI API connection error: {str(e)}")
        raise RuntimeError(f"Anslutningsfel till OpenAI API: {str(e)}")
        
    except ValueError as e:
        logger.error(f"Value error during transcription: {str(e)}")
        raise
        
    except Exception as e:
        # Log the actual error for debugging
        logger.error(f"Unexpected error during transcription: {str(e)}", exc_info=True)
        raise RuntimeError(f"Error during transcription: {str(e)}")