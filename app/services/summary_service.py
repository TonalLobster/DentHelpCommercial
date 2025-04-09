"""
Summary service for generating structured summaries of dental transcriptions.
Med stöd för framstegsrapportering.
"""
import os
import logging
import json
import time
import openai
from flask import current_app
from app.utils.progress_tracker import update_task_status

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

def generate_summary(transcription, task_id=None):
    """
    Generates a structured summary of a dental transcription using GPT.
    
    Args:
        transcription: Transcribed text from the meeting
        task_id: ID för framstegsspårning (valfritt)
        
    Returns:
        dict: Structured summary with categories
    """
    try:
        # Uppdatera status om task_id finns
        if task_id:
            update_task_status(
                task_id, 
                progress=60, 
                status='summarizing',
                message='Startar AI-sammanfattning av transkription...',
                step='summary', 
                step_status='active',
                time_left=15
            )
        
        # Try to get API key
        api_key = get_api_key()
        
        if not api_key:
            error_msg = "OpenAI API key missing. Check environment variables or app configuration."
            logger.error(error_msg)
            
            if task_id:
                update_task_status(
                    task_id,
                    status='error',
                    message=error_msg,
                    step='summary', 
                    step_status='error',
                    error=error_msg
                )
                
            raise ValueError(error_msg)
        
        # Create client with API key
        try:
            client = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI klient skapad")
            
            if task_id:
                update_task_status(
                    task_id,
                    progress=65,
                    message='AI-tjänst ansluten, analyserar transkription...',
                    time_left=12
                )
                
        except Exception as e:
            error_msg = f"Kunde inte skapa OpenAI-klient: {str(e)}"
            logger.error(error_msg)
            
            if task_id:
                update_task_status(
                    task_id,
                    status='error',
                    message=error_msg,
                    step='summary', 
                    step_status='error',
                    error=error_msg
                )
                
            raise RuntimeError(error_msg)
        
        # Mät transkriptionens längd för framstegsrapportering
        transcription_length = len(transcription)
        if task_id:
            update_task_status(
                task_id,
                progress=70,
                message=f'Analyserar {transcription_length} tecken av transkriberad text...',
                time_left=10
            )
        
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
        
        for i, model in enumerate(available_models):
            try:
                if task_id:
                    update_task_status(
                        task_id,
                        progress=75 + i*5,
                        message=f'Använder {model} för sammanfattning...',
                        time_left=10 - i*3
                    )
                    
                logger.info(f"Försöker använda modell: {model}")
                
                # Lägg till lite fördröjning för att visa progress för användaren
                # (i en riktig implementation skulle detta vara naturlig väntetid från API)
                if task_id:
                    time.sleep(0.5)
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
                
                summary_json = response.choices[0].message.content
                logger.info(f"Svar mottaget från OpenAI ({model})")
                
                if task_id:
                    update_task_status(
                        task_id,
                        progress=85,
                        message='Svar mottaget från AI, bearbetar sammanfattning...',
                        time_left=3
                    )
                
                # Rensa bort eventuella extra tecken före JSON
                if '```json' in summary_json:
                    summary_json = summary_json.split('```json')[1].split('```')[0].strip()
                elif '```' in summary_json:
                    summary_json = summary_json.split('```')[1].split('```')[0].strip()
                
                # Parsa JSON
                summary_dict = json.loads(summary_json)
                logger.info("JSON framgångsrikt parsad")
                
                if task_id:
                    update_task_status(
                        task_id,
                        progress=90,
                        message='Sammanfattning slutförd!',
                        step='summary', 
                        step_status='completed',
                        time_left=2
                    )
                    
                return summary_dict
                
            except Exception as e:
                logger.warning(f"Kunde inte använda {model}: {str(e)}")
                
                if task_id:
                    update_task_status(
                        task_id,
                        message=f'Varning: Kunde inte använda {model}, provar alternativ...',
                    )
                    
                last_error = e
                continue
        
        # Om vi kommer hit har alla modeller misslyckats
        error_msg = f"Alla AI-modeller misslyckades: {str(last_error) if last_error else 'Okänt fel'}"
        logger.error(error_msg)
        
        if task_id:
            update_task_status(
                task_id,
                status='error',
                message=error_msg,
                step='summary', 
                step_status='error',
                error=error_msg
            )
            
        if last_error:
            raise last_error
        else:
            raise RuntimeError("Alla modeller misslyckades utan specifikt fel")
            
    except json.JSONDecodeError as json_error:
        error_msg = f"JSON parse error: {str(json_error)}"
        logger.error(error_msg)
        
        if task_id:
            update_task_status(
                task_id,
                status='error',
                message=error_msg,
                step='summary', 
                step_status='error',
                error=error_msg
            )
        
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
        error_msg = f"OpenAI API rate limit exceeded: {str(e)}"
        logger.error(error_msg)
        
        if task_id:
            update_task_status(
                task_id,
                status='error',
                message=error_msg,
                step='summary', 
                step_status='error',
                error=error_msg
            )
            
        return create_error_response("API-gränsen för OpenAI överskriden")
        
    except openai.APIError as e:
        error_msg = f"OpenAI API error: {str(e)}"
        logger.error(error_msg)
        
        if task_id:
            update_task_status(
                task_id,
                status='error',
                message=error_msg,
                step='summary', 
                step_status='error',
                error=error_msg
            )
            
        return create_error_response("OpenAI API-fel")
        
    except openai.APIConnectionError as e:
        error_msg = f"OpenAI API connection error: {str(e)}"
        logger.error(error_msg)
        
        if task_id:
            update_task_status(
                task_id,
                status='error',
                message=error_msg,
                step='summary', 
                step_status='error',
                error=error_msg
            )
            
        return create_error_response("Anslutningsfel till OpenAI API")
        
    except ValueError as e:
        error_msg = f"Value error during summary generation: {str(e)}"
        logger.error(error_msg)
        
        if task_id:
            update_task_status(
                task_id,
                status='error',
                message=error_msg,
                step='summary', 
                step_status='error',
                error=error_msg
            )
            
        return create_error_response(f"Valideringsfel: {str(e)}")
        
    except Exception as e:
        error_msg = f"Unexpected error during summary generation: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        if task_id:
            update_task_status(
                task_id,
                status='error',
                message=error_msg,
                step='summary', 
                step_status='error',
                error=error_msg
            )
            
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