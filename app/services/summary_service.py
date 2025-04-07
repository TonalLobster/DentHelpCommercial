"""
Summary service for generating structured summaries of dental transcriptions.
"""
import os
import logging
import json
import openai
from flask import current_app

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("summary_service")

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

        # Försök med olika modeller i prioritetsordning
        available_models = ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]
        last_error = None
        
        for model in available_models:
            try:
                logger.info(f"Försöker använda modell: {model}")
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
                
                summary_json = response.choices[0].message.content
                logger.info(f"Svar mottaget från OpenAI ({model})")
                
                # Rensa bort eventuella extra tecken före JSON
                if '```json' in summary_json:
                    summary_json = summary_json.split('```json')[1].split('```')[0].strip()
                elif '```' in summary_json:
                    summary_json = summary_json.split('```')[1].split('```')[0].strip()
                
                # Parsa JSON
                summary_dict = json.loads(summary_json)
                logger.info("JSON framgångsrikt parsad")
                return summary_dict
                
            except Exception as e:
                logger.warning(f"Kunde inte använda {model}: {str(e)}")
                last_error = e
                continue
        
        # Om vi kommer hit har alla modeller misslyckats
        if last_error:
            raise last_error
        else:
            raise RuntimeError("Alla modeller misslyckades utan specifikt fel")
            
    except json.JSONDecodeError as json_error:
        logger.error(f"JSON parse error: {str(json_error)}")
        
        # Fallback struktur om JSON parsing misslyckas
        logger.warning("Använder fallback-struktur på grund av JSON-fel")
        return {
            "anamnes": "Ej dokumenterat (JSON-fel)",
            "status": "Ej dokumenterat (JSON-fel)",
            "diagnos": "Ej dokumenterat (JSON-fel)",
            "åtgärd": "Ej dokumenterat (JSON-fel)",
            "behandlingsplan": "Ej dokumenterat (JSON-fel)",
            "kommunikation": "Ej dokumenterat (JSON-fel)"
        }
    except openai.RateLimitError as e:
        logger.error(f"OpenAI API rate limit exceeded: {str(e)}")
        return create_error_response("API-gränsen för OpenAI överskriden")
        
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return create_error_response("OpenAI API-fel")
        
    except openai.APIConnectionError as e:
        logger.error(f"OpenAI API connection error: {str(e)}")
        return create_error_response("Anslutningsfel till OpenAI API")
        
    except ValueError as e:
        logger.error(f"Value error during summary generation: {str(e)}")
        return create_error_response(f"Valideringsfel: {str(e)}")
        
    except Exception as e:
        logger.error(f"Unexpected error during summary generation: {str(e)}", exc_info=True)
        return create_error_response(f"Oväntat fel: {str(e)}")

def create_error_response(error_message):
    """Creates a standardized error response."""
    return {
        "anamnes": f"Ej dokumenterat ({error_message})",
        "status": f"Ej dokumenterat ({error_message})",
        "diagnos": f"Ej dokumenterat ({error_message})",
        "åtgärd": f"Ej dokumenterat ({error_message})",
        "behandlingsplan": f"Ej dokumenterat ({error_message})",
        "kommunikation": f"Ej dokumenterat ({error_message})"
    }