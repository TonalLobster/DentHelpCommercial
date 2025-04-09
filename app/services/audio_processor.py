import os
import tempfile
import logging
from io import BytesIO
import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from pydub.effects import low_pass_filter
from app.utils.progress_tracker import update_task_status, format_size

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("audio_processor")

def save_uploaded_file(audio_file):
    """Sparar en uppladdad fil till en temporär fil på disk."""
    try:
        # Bestäm filändelse
        name = getattr(audio_file, 'name', 'audio_file')
        file_extension = os.path.splitext(name)[1] if '.' in name else '.wav'
        
        # Skapa temporär fil
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            temp_path = temp_file.name
            
            # Läs innehållet från filen
            if hasattr(audio_file, 'read'):
                audio_file.seek(0)  # Återställ läsposition
                content = audio_file.read()
            elif hasattr(audio_file, 'getvalue'):
                content = audio_file.getvalue()
            else:
                content = audio_file
                
            # Skriv till temporär fil
            temp_file.write(content)
            
            # Återställ läsposition för eventuell återanvändning
            if hasattr(audio_file, 'seek'):
                audio_file.seek(0)
        
        logger.info(f"Sparade uppladdad fil till: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Fel vid sparande av uppladdad fil: {str(e)}")
        raise

def process_audio(audio_file, task_id=None):
    """
    Bearbetar en ljudfil för optimal transkribering.
    
    Args:
        audio_file: Fil-liknande objekt med ljuddata
        task_id: ID för framstegsspårning (valfritt)
        
    Returns:
        BytesIO: Optimerad ljuddata redo för transkribering
    """
    logger.info("Startar ljudbearbetning...")
    
    # Uppdatera status om task_id ges
    if task_id:
        update_task_status(
            task_id, 
            progress=0,
            status='processing',
            message='Startar ljudbearbetning...',
            step='compression', 
            step_status='active'
        )
    
    try:
        # Hantera olika typer av indata
        if hasattr(audio_file, 'name'):
            logger.info(f"Bearbetar fil av typ: {type(audio_file).__name__}, namn: {audio_file.name}")
        else:
            logger.info(f"Bearbetar fil av typ: {type(audio_file).__name__}")
        
        # Uppdatera status
        if task_id:
            update_task_status(
                task_id,
                progress=5,
                message='Förbereder ljudfil för bearbetning...',
                time_left=20
            )
        
        # Spara filen tillfälligt för att undvika kompatibilitetsproblem
        temp_path = save_uploaded_file(audio_file)
        
        # Hämta original filstorlek
        orig_size = os.path.getsize(temp_path)
        
        # Uppdatera status med filstorlek
        if task_id:
            update_task_status(
                task_id,
                progress=10,
                message=f'Förbehandlar ljudfil ({format_size(orig_size)})...',
                time_left=15,
                size_info={'original': orig_size}
            )
        
        try:
            # Bearbeta filen med optimize_for_whisper
            processed_path = optimize_for_whisper(temp_path, task_id=task_id)
            
            # Kontrollera att filen existerar och har innehåll
            if not os.path.exists(processed_path) or os.path.getsize(processed_path) == 0:
                error_msg = f"Bearbetad fil saknas eller är tom: {processed_path}"
                logger.error(error_msg)
                
                if task_id:
                    update_task_status(
                        task_id,
                        status='error',
                        message=error_msg,
                        error=error_msg
                    )
                
                raise RuntimeError("Bearbetad ljudfil är tom eller misslyckades att skapas")
            
            # Hämta komprimerad filstorlek
            comp_size = os.path.getsize(processed_path)
            
            # Uppdatera status med slutresultat
            if task_id:
                compression_pct = (1 - (comp_size / orig_size)) * 100 if orig_size > 0 else 0
                update_task_status(
                    task_id,
                    progress=20,
                    message=f'Komprimering slutförd: {format_size(orig_size)} → {format_size(comp_size)} ({compression_pct:.1f}% reduktion)',
                    step='compression', 
                    step_status='completed',
                    time_left=5,
                    size_info={'compressed': comp_size}
                )
            
            # Läs in den bearbetade filen
            with open(processed_path, 'rb') as f:
                processed_audio = BytesIO(f.read())
                processed_audio.name = os.path.basename(processed_path)
            
            # Ta bort temporära filer
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(processed_path) and processed_path != temp_path:
                os.remove(processed_path)
            
            logger.info("Ljudbearbetning slutförd framgångsrikt")
            return processed_audio, None
            
        except Exception as e:
            logger.error(f"Fel vid bearbetning: {str(e)}")
            
            if task_id:
                update_task_status(
                    task_id,
                    progress=15,
                    message=f'Varning: Optimering misslyckades - använder originalfil: {str(e)}',
                    error=str(e)
                )
            
            # Fallback: om bearbetningen misslyckas, returnera ursprungliga filen
            logger.info("Använder obearbetad fil som fallback")
            with open(temp_path, 'rb') as f:
                original_audio = BytesIO(f.read())
                original_audio.name = os.path.basename(temp_path)
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            return original_audio, str(e)
            
    except Exception as e:
        error_msg = f"Kritiskt fel i process_audio: {str(e)}"
        logger.error(error_msg)
        
        if task_id:
            update_task_status(
                task_id,
                status='error',
                message=error_msg,
                step='compression', 
                step_status='error',
                error=error_msg
            )
            
        raise RuntimeError(f"Ljudbearbetningsfel: {str(e)}")

def optimize_for_whisper(input_path, max_size_mb=24, task_id=None):
    """
    Optimerar en ljudfil för Whisper API genom att:
    1. Identifiera och bevara talsegment
    2. Ta bort tystnad
    3. Normalisera ljudet
    4. Konvertera till mono 16kHz
    5. Exportera som mp3
    
    Args:
        input_path: Sökväg till indatafilen
        max_size_mb: Maximal filstorlek i MB
        task_id: ID för framstegsspårning (valfritt)
        
    Returns:
        str: Sökväg till den optimerade filen
    """
    try:
        logger.info(f"Optimerar fil för Whisper: {input_path}")
        
        # Verifiera att filen existerar
        if not os.path.exists(input_path):
            error_msg = f"Indatafilen existerar inte: {input_path}"
            
            if task_id:
                update_task_status(
                    task_id,
                    status='error',
                    message=error_msg,
                    error=error_msg
                )
                
            raise RuntimeError(error_msg)
        
        # Läs in ljudfilen
        try:
            if task_id:
                update_task_status(
                    task_id,
                    progress=12,
                    message="Läser in ljudfil...",
                    time_left=15
                )
                
            audio = AudioSegment.from_file(input_path)
        except Exception as e:
            logger.error(f"Kunde inte läsa in ljudfil: {str(e)}")
            
            if task_id:
                update_task_status(
                    task_id,
                    progress=12,
                    message="Provar alternativa ljudformat...",
                    time_left=15
                )
            
            # Försök med olika format
            for format in ['wav', 'mp3', 'm4a', 'ogg']:
                try:
                    logger.info(f"Försöker läsa in som {format}")
                    audio = AudioSegment.from_file(input_path, format=format)
                    
                    if task_id:
                        update_task_status(
                            task_id,
                            message=f"Ljudfil inläst som {format}-format",
                        )
                        
                    break
                except Exception:
                    continue
            else:
                error_msg = f"Kunde inte läsa in ljudfilen i något av de vanligaste formaten: {str(e)}"
                
                if task_id:
                    update_task_status(
                        task_id,
                        status='error',
                        message=error_msg,
                        error=error_msg
                    )
                    
                raise RuntimeError(error_msg)
        
        # Logga ursprunglig ljudinformation
        original_duration = len(audio) / 1000
        logger.info(f"Inläst ljud: {original_duration:.2f}s, {audio.channels} kanaler, {audio.frame_rate}Hz")
        
        if task_id:
            update_task_status(
                task_id,
                progress=14,
                message=f"Ljudfil inläst: {original_duration:.1f}s, {audio.channels} kanaler",
                time_left=14
            )
        
        # Ta bort tystnad, bevara talsegment
        if task_id:
            update_task_status(
                task_id,
                progress=15,
                message="Identifierar talsegment och tar bort tystnad...",
                time_left=12
            )
            
        nonsilent = detect_nonsilent(
            audio, 
            silence_thresh=-45,
            min_silence_len=1000,
            seek_step=100
        )
        
        if len(nonsilent) == 0:
            logger.warning("Inga icke-tysta segment hittades, använder hela filen")
            
            if task_id:
                update_task_status(
                    task_id,
                    message="Inga tydliga talsegment identifierade - använder hela ljudfilen",
                )
                
            processed = audio
        else:
            # Konkatanera endast icke-tysta segment
            processed = AudioSegment.empty()
            
            if task_id:
                update_task_status(
                    task_id,
                    progress=16,
                    message=f"Bearbetar {len(nonsilent)} talsegment...",
                    time_left=10
                )
                
            for i, (start, end) in enumerate(nonsilent):
                if i % 5 == 0 and task_id:  # Uppdatera var 5:e segment för att inte överbelasta
                    update_task_status(
                        task_id,
                        progress=16 + min(2, int(3 * i / len(nonsilent))),
                        message=f"Bearbetar talsegment {i+1}/{len(nonsilent)}...",
                        time_left=10 - min(5, int(5 * i / len(nonsilent)))
                    )
                    
                if len(processed) > 0:
                    processed += AudioSegment.silent(duration=100)
                processed += audio[start:end]
            
            # Lägg till små tystandsbuffertar
            processed = AudioSegment.silent(duration=300) + processed + AudioSegment.silent(duration=300)
        
        # Beräkna faktisk talduration
        speech_duration = len(processed) / 1000
        logger.info(f"Bevarad talduration: {speech_duration:.2f}s")
        
        if task_id:
            update_task_status(
                task_id,
                progress=18,
                message=f"Talduration: {speech_duration:.1f}s ({speech_duration/original_duration*100:.1f}% av originalet)",
                time_left=8
            )
        
        # Ljudbearbetning
        if task_id:
            update_task_status(
                task_id,
                progress=19,
                message="Bearbetar ljud (filtrering, normalisering, konvertering)...",
                time_left=6
            )
            
        processed = low_pass_filter(processed, 4000)
        processed = processed.set_channels(1).set_frame_rate(16000)
        
        # Skapa unikt filnamn för utdata
        output_path = os.path.join(
            tempfile.gettempdir(), 
            f"processed_audio_{os.getpid()}_{np.random.randint(1000, 9999)}.mp3"
        )
        
        # Säkerställ att temporär katalog existerar
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        
        # Exportera med kompression och bättre felhantering
        if task_id:
            update_task_status(
                task_id,
                progress=20,
                message="Komprimerar och sparar bearbetad ljudfil...",
                time_left=5
            )
            
        try:
            logger.info("Försöker exportera med 32k bitrate")
            processed.export(output_path, format="mp3", bitrate="32k")
        except Exception as e:
            logger.error(f"Fel vid export med 32k bitrate: {str(e)}")
            
            if task_id:
                update_task_status(
                    task_id,
                    message="Provar lägre bitrate för bättre kompatibilitet...",
                )
            
            # Försök med en lägre bitrate
            try:
                logger.info("Försöker med lägre bitrate (16k)")
                processed.export(output_path, format="mp3", bitrate="16k")
            except Exception as e2:
                logger.error(f"Fel vid export med 16k bitrate: {str(e2)}")
                
                if task_id:
                    update_task_status(
                        task_id,
                        message="Provar ännu lägre bitrate...",
                    )
                
                # Försök med ännu lägre bitrate
                try:
                    logger.info("Försöker med ännu lägre bitrate (8k)")
                    processed.export(output_path, format="mp3", bitrate="8k")
                except Exception as e3:
                    logger.error(f"Fel vid export med 8k bitrate: {str(e3)}")
                    
                    if task_id:
                        update_task_status(
                            task_id,
                            message="Exporterar som WAV-format istället...",
                        )
                    
                    # Sista försök: exportera som wav
                    wav_path = output_path.replace(".mp3", ".wav")
                    logger.info(f"Försöker exportera som WAV: {wav_path}")
                    processed.export(wav_path, format="wav")
                    output_path = wav_path
        
        # Kontrollera filstorlek
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"Slutlig filstorlek: {size_mb:.2f} MB")
            
            if task_id:
                update_task_status(
                    task_id,
                    progress=22,
                    message=f"Fil exporterad: {size_mb:.2f} MB",
                    time_left=3
                )
            
            # Om filen fortfarande är för stor, försök med mer aggressiv komprimering
            if size_mb > max_size_mb and output_path.endswith('.mp3'):
                logger.warning(f"Varning: Filstorlek ({size_mb:.2f} MB) överstiger gränsen på {max_size_mb} MB")
                
                if task_id:
                    update_task_status(
                        task_id,
                        message=f"Filen är för stor ({size_mb:.2f} MB). Utför ytterligare komprimering...",
                        time_left=5
                    )
                
                logger.info("Försöker med mer aggressiv komprimering (mono, 8kHz, 8k bitrate)")
                
                # Konvertera till mono och lägre samplingshastighet
                try:
                    lower_rate = processed.set_frame_rate(8000)
                    lower_rate_path = output_path.replace(".mp3", "_low.mp3")
                    lower_rate.export(lower_rate_path, format="mp3", bitrate="8k")
                    
                    # Om exporten lyckas, använd den lägre kvalitetsversionen
                    if os.path.exists(lower_rate_path) and os.path.getsize(lower_rate_path) > 0:
                        # Ta bort den ursprungliga filen
                        os.remove(output_path)
                        output_path = lower_rate_path
                        size_mb = os.path.getsize(output_path) / (1024 * 1024)
                        logger.info(f"Ny filstorlek efter aggressiv komprimering: {size_mb:.2f} MB")
                        
                        if task_id:
                            update_task_status(
                                task_id,
                                message=f"Komprimering slutförd: {size_mb:.2f} MB",
                            )
                except Exception as e:
                    logger.error(f"Kunde inte utföra aggressiv komprimering: {str(e)}")
                    
                    if task_id:
                        update_task_status(
                            task_id,
                            message=f"Varning: Kunde inte utföra ytterligare komprimering: {str(e)}",
                            error=str(e)
                        )
        else:
            error_msg = f"Utdatafilen existerar inte: {output_path}"
            logger.error(error_msg)
            
            if task_id:
                update_task_status(
                    task_id,
                    status='error',
                    message=error_msg,
                    error=error_msg
                )
                
            raise RuntimeError(f"Utdatafilen kunde inte skapas: {output_path}")
        
        # Dela upp filen om den fortfarande är för stor
        if size_mb > 24:
            logger.warning("Filen är fortfarande för stor för Whisper API (>24MB)")
            
            if task_id:
                update_task_status(
                    task_id,
                    message=f"Varning: Filen är stor ({size_mb:.2f} MB) vilket kan påverka transkriptionskvaliteten",
                )
                
            logger.info("Denna stora fil kan orsaka problem med Whisper API")
        
        return output_path
        
    except Exception as e:
        error_msg = f"Optimeringsfel: {str(e)}"
        logger.error(error_msg)
        
        if task_id:
            update_task_status(
                task_id,
                status='error',
                message=error_msg,
                step='compression', 
                step_status='error',
                error=error_msg
            )
            
        raise RuntimeError(f"Optimeringsfel: {str(e)}")

# Test module when run directly
if __name__ == "__main__":
    logging.info("Testar audio_processor...")
    try:
        # Skapa en testfil med tystnad
        test_audio = AudioSegment.silent(duration=1000)
        test_audio = test_audio.set_channels(1).set_frame_rate(16000)
        test_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        test_path = test_file.name
        test_file.close()
        
        test_audio.export(test_path, format="wav")
        
        # Testa process_audio
        with open(test_path, "rb") as f:
            test_bytes = BytesIO(f.read())
            test_bytes.name = "test_audio.wav"
            
            result, error = process_audio(test_bytes)
            if error:
                logging.error(f"Test misslyckades: {error}")
            else:
                logging.info("Test lyckades!")
        
        # Städa upp
        os.remove(test_path)
        
    except Exception as e:
        logging.error(f"Testfel: {str(e)}")