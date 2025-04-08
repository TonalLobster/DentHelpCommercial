import os
import tempfile
import logging
from io import BytesIO
import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from pydub.effects import low_pass_filter

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

def process_audio(audio_file):
    """
    Bearbetar en ljudfil för optimal transkribering.
    
    Args:
        audio_file: Fil-liknande objekt med ljuddata
        
    Returns:
        BytesIO: Optimerad ljuddata redo för transkribering
    """
    logger.info("Startar ljudbearbetning...")
    
    try:
        # Hantera olika typer av indata
        if hasattr(audio_file, 'name'):
            logger.info(f"Bearbetar fil av typ: {type(audio_file).__name__}, namn: {audio_file.name}")
        else:
            logger.info(f"Bearbetar fil av typ: {type(audio_file).__name__}")
        
        # Spara filen tillfälligt för att undvika kompatibilitetsproblem
        temp_path = save_uploaded_file(audio_file)
        
        try:
            # Bearbeta filen med optimize_for_whisper
            processed_path = optimize_for_whisper(temp_path)
            
            # Kontrollera att filen existerar och har innehåll
            if not os.path.exists(processed_path) or os.path.getsize(processed_path) == 0:
                logger.error(f"Bearbetad fil saknas eller är tom: {processed_path}")
                raise RuntimeError("Bearbetad ljudfil är tom eller misslyckades att skapas")
            
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
            
            # Fallback: om bearbetningen misslyckas, returnera ursprungliga filen
            logger.info("Använder obearbetad fil som fallback")
            with open(temp_path, 'rb') as f:
                original_audio = BytesIO(f.read())
                original_audio.name = os.path.basename(temp_path)
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            return original_audio, str(e)
            
    except Exception as e:
        logger.error(f"Kritiskt fel i process_audio: {str(e)}")
        raise RuntimeError(f"Ljudbearbetningsfel: {str(e)}")

def optimize_for_whisper(input_path, max_size_mb=24):
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
        
    Returns:
        str: Sökväg till den optimerade filen
    """
    try:
        logger.info(f"Optimerar fil för Whisper: {input_path}")
        
        # Verifiera att filen existerar
        if not os.path.exists(input_path):
            raise RuntimeError(f"Indatafilen existerar inte: {input_path}")
        
        # Läs in ljudfilen
        try:
            audio = AudioSegment.from_file(input_path)
        except Exception as e:
            logger.error(f"Kunde inte läsa in ljudfil: {str(e)}")
            
            # Försök med olika format
            for format in ['wav', 'mp3', 'm4a', 'ogg']:
                try:
                    logger.info(f"Försöker läsa in som {format}")
                    audio = AudioSegment.from_file(input_path, format=format)
                    break
                except Exception:
                    continue
            else:
                raise RuntimeError(f"Kunde inte läsa in ljudfilen i något av de vanligaste formaten: {str(e)}")
        
        # Logga ursprunglig ljudinformation
        original_duration = len(audio) / 1000
        logger.info(f"Inläst ljud: {original_duration:.2f}s, {audio.channels} kanaler, {audio.frame_rate}Hz")
        
        # Ta bort tystnad, bevara talsegment
        nonsilent = detect_nonsilent(
            audio, 
            silence_thresh=-45,
            min_silence_len=1000,
            seek_step=100
        )
        
        if len(nonsilent) == 0:
            logger.warning("Inga icke-tysta segment hittades, använder hela filen")
            processed = audio
        else:
            # Konkatanera endast icke-tysta segment
            processed = AudioSegment.empty()
            for start, end in nonsilent:
                if len(processed) > 0:
                    processed += AudioSegment.silent(duration=100)
                processed += audio[start:end]
            
            # Lägg till små tystandsbuffertar
            processed = AudioSegment.silent(duration=300) + processed + AudioSegment.silent(duration=300)
        
        # Beräkna faktisk talduration
        speech_duration = len(processed) / 1000
        logger.info(f"Bevarad talduration: {speech_duration:.2f}s")
        
        # Ljudbearbetning
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
        try:
            logger.info("Försöker exportera med 32k bitrate")
            processed.export(output_path, format="mp3", bitrate="32k")
        except Exception as e:
            logger.error(f"Fel vid export med 32k bitrate: {str(e)}")
            
            # Försök med en lägre bitrate
            try:
                logger.info("Försöker med lägre bitrate (16k)")
                processed.export(output_path, format="mp3", bitrate="16k")
            except Exception as e2:
                logger.error(f"Fel vid export med 16k bitrate: {str(e2)}")
                
                # Försök med ännu lägre bitrate
                try:
                    logger.info("Försöker med ännu lägre bitrate (8k)")
                    processed.export(output_path, format="mp3", bitrate="8k")
                except Exception as e3:
                    logger.error(f"Fel vid export med 8k bitrate: {str(e3)}")
                    
                    # Sista försök: exportera som wav
                    wav_path = output_path.replace(".mp3", ".wav")
                    logger.info(f"Försöker exportera som WAV: {wav_path}")
                    processed.export(wav_path, format="wav")
                    output_path = wav_path
        
        # Kontrollera filstorlek
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"Slutlig filstorlek: {size_mb:.2f} MB")
            
            # Om filen fortfarande är för stor, försök med mer aggressiv komprimering
            if size_mb > max_size_mb and output_path.endswith('.mp3'):
                logger.warning(f"Varning: Filstorlek ({size_mb:.2f} MB) överstiger gränsen på {max_size_mb} MB")
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
                except Exception as e:
                    logger.error(f"Kunde inte utföra aggressiv komprimering: {str(e)}")
        else:
            logger.error(f"Utdatafilen existerar inte: {output_path}")
            raise RuntimeError(f"Utdatafilen kunde inte skapas: {output_path}")
        
        # Dela upp filen om den fortfarande är för stor
        if size_mb > 24:
            logger.warning("Filen är fortfarande för stor för Whisper API (>24MB)")
            logger.info("Denna stora fil kan orsaka problem med Whisper API")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Optimeringsfel: {str(e)}")
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