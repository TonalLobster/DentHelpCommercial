"""
Transcription service for converting audio to text using OpenAI's Whisper API.
"""
import os
import logging
import tempfile
from io import BytesIO
import openai
from flask import current_app
import json

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

def generate_summary(transcription):
    """
    Generates a structured summary of a dental transcription using GPT.
    
    Args:
        transcription: Transcribed text from the meeting
        
    Returns:
        dict: Structured summary with categories
    """
    try:
        # Try to get API key
        api_key = get_api_key()
        
        if not api_key:
            raise ValueError("OpenAI API key missing. Check environment variables or app configuration.")
        
        # Create client with API key
        client = openai.OpenAI(api_key=api_key)
        
        # Prompt with specific instructions for dental summaries
        prompt = (
            'Sammanfatta detta tandläkarmöte på svenska i ett strukturerat journalformat. Följ dessa regler:\n'
            '1. Använd ISO 3950-notation (11-48) för tänder\n'
            '2. För områden utan specifik tand, använd: Q1 (övre höger 11-18), Q2 (övre vänster 21-28), '
            'Q3 (nedre vänster 31-38), Q4 (nedre höger 41-48)\n'
            '3. Använd standardförkortningar: Rtg = Röntgen, DH = Dentalhygienist, Pat = Patient, '
            'ua = Utan anmärkning, EPT = Elektrisk pulpatest, BW = Bitewing\n'
            '4. Om information saknas, ange "Ej dokumenterat"\n'
            '5. Returnera i detta JSON-format:\n'
            '{\n'
            '  "anamnes": "[patientens symtom och historik]",\n'
            '  "status": "[kliniska fynd]",\n'
            '  "diagnos": "[ställd diagnos]",\n'
            '  "åtgärd": "[utförd behandling]",\n'
            '  "behandlingsplan": "[planerade åtgärder]",\n'
            '  "kommunikation": "[informerat patienten]"\n'
            '}\n\n'
            f'Transkription: {transcription}\n'
            'Returnera endast JSON-objektet.'
        )
        
        response = client.chat.completions.create(
            model="gpt-4o",  # Or fallback to gpt-4
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        summary_json = response.choices[0].message.content
        
        # Remove potential code block formatting
        if '```json' in summary_json:
            summary_json = summary_json.split('```json')[1].split('```')[0].strip()
        
        # Parse and return JSON
        return json.loads(summary_json)
        
    except json.JSONDecodeError as json_error:
        logger.error(f"JSON parse error: {str(json_error)}")
        
        # Fallback structure if JSON parsing fails
        return {
            "anamnes": "Ej dokumenterat (JSON-fel)",
            "status": "Ej dokumenterat (JSON-fel)",
            "diagnos": "Ej dokumenterat (JSON-fel)",
            "åtgärd": "Ej dokumenterat (JSON-fel)",
            "behandlingsplan": "Ej dokumenterat (JSON-fel)",
            "kommunikation": "Ej dokumenterat (JSON-fel)"
        }
    except Exception as e:
        logger.error(f"Summary generation error: {str(e)}")
        
        # Generic error fallback
        return {
            "anamnes": "Ej dokumenterat (generellt fel)",
            "status": "Ej dokumenterat (generellt fel)",
            "diagnos": "Ej dokumenterat (generellt fel)",
            "åtgärd": "Ej dokumenterat (generellt fel)",
            "behandlingsplan": "Ej dokumenterat (generellt fel)",
            "kommunikation": "Ej dokumenterat (generellt fel)"
        }