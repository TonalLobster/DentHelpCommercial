"""
Transcription service för konvertering av ljud till text med OpenAI Whisper API.
"""
import os
import logging
import tempfile
from io import BytesIO
import openai
from flask import current_app

logger = logging.getLogger(__name__)

def get_api_key():
    """Hämta OpenAI API-nyckel från miljö eller app-konfiguration."""
    if api_key := os.environ.get("OPENAI_API_KEY"):
        logger.info("Använder API-nyckel från miljövariabel")
        return api_key
    
    if hasattr(current_app, 'config') and current_app.config.get('OPENAI_API_KEY'):
        logger.info("Använder API-nyckel från Flask-app konfiguration")
        return current_app.config['OPENAI_API_KEY']
    
    logger.warning("Ingen API-nyckel hittades")
    return None

def transcribe_audio(audio_file):
    """
    Transkribera en ljudfil med OpenAI Whisper API.
    
    Args:
        audio_file: Ett BytesIO-objekt eller fil-liknande objekt med ljuddata
        
    Returns:
        str: Transkriberad text
    """
    try:
        # Hämta API-nyckel
        api_key = get_api_key()
            
        if not api_key:
            raise ValueError("OpenAI API-nyckel saknas. Kontrollera miljövariabler eller app-konfiguration.")
        
        # Skapa klient med API-nyckel
        client = openai.OpenAI(api_key=api_key)
        logger.info("OpenAI klient skapad")
        
        # Hantera olika typer av indata
        temp_file = None
        try:
            # Logga vad vi arbetar med
            if isinstance(audio_file, BytesIO):
                logger.info("Processerar ljudfil av typ: BytesIO")
            elif hasattr(audio_file, 'read'):
                logger.info(f"Processerar ljudfil av typ: {type(audio_file).__name__}")
            else:
                logger.info(f"Processerar ljudfil av typ: {type(audio_file)}")
            
            if hasattr(audio_file, 'read'):
                # Återställ läshuvudet till början av filen om det är ett filliknande objekt
                audio_file.seek(0)
                logger.info("Återställde filpekaren till början")
                
                # Om det är ett filliknande objekt som inte är BytesIO, spara det tillfälligt
                if not isinstance(audio_file, BytesIO):
                    logger.info("Skapar temporär fil för icke-BytesIO objekt")
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    temp_file.write(audio_file.read())
                    temp_file.close()
                    audio_file.seek(0)  # Återställ läshuvudet igen
                    logger.info(f"Temporär fil skapad: {temp_file.name}")
                    
                    # Öppna den tillfälliga filen
                    with open(temp_file.name, 'rb') as f:
                        logger.info("Skickar transkriptionsbegäran till OpenAI (från temp file)")
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                            language="sv"  # Svenska
                        )
                else:
                    # Om det är en BytesIO, försök använda den direkt
                    try:
                        logger.info("Skickar transkriptionsbegäran till OpenAI (direkt BytesIO)")
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language="sv"  # Svenska
                        )
                    except Exception as e:
                        logger.error(f"Fel vid direkt BytesIO transaktion: {str(e)}")
                        
                        # Fallback: Spara BytesIO till temporär fil
                        logger.info("Försöker med fallback till temporär fil för BytesIO")
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                        temp_file.write(audio_file.getvalue())
                        temp_file.close()
                        audio_file.seek(0)  # Återställ läshuvudet igen
                        
                        with open(temp_file.name, 'rb') as f:
                            logger.info("Skickar transkriptionsbegäran till OpenAI (fallback från BytesIO)")
                            transcription = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=f,
                                language="sv"  # Svenska
                            )
            else:
                # Om det inte är ett filliknande objekt, anta att det är en sökväg
                logger.info(f"Skickar transkriptionsbegäran till OpenAI från sökväg: {audio_file}")
                with open(audio_file, 'rb') as f:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="sv"  # Svenska
                    )
                    
            logger.info("Transkribering slutförd framgångsrikt")
            return transcription.text
            
        finally:
            # Ta bort temporär fil om den skapades
            if temp_file and os.path.exists(temp_file.name):
                logger.info(f"Tar bort temporär fil: {temp_file.name}")
                os.unlink(temp_file.name)
                
    except openai.OpenAIError as oe:
        # Logga OpenAI-specifika fel
        error_msg = f"OpenAI API-fel: Error code: {oe.status_code} - {oe.response or str(oe)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        # Logga det faktiska felet för felsökning
        logger.error(f"Transkriptionsfel: {str(e)}")
        raise RuntimeError(f"Fel under transkribering: {str(e)}")