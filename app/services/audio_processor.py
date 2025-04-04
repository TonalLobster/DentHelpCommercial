"""
Audio processing service for optimizing audio files for transcription.
"""
import os
import tempfile
from io import BytesIO
import logging
import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from pydub.effects import low_pass_filter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("audio_processor")

def setup_ffmpeg():
    """Configure pydub with correct FFmpeg paths"""
    # Try to find FFmpeg in common locations
    if "FFMPEG_PATH" in os.environ and os.path.exists(os.environ["FFMPEG_PATH"]):
        AudioSegment.converter = os.environ["FFMPEG_PATH"]
    elif os.path.exists("/usr/bin/ffmpeg"):
        AudioSegment.converter = "/usr/bin/ffmpeg"
    
    if "FFPROBE_PATH" in os.environ and os.path.exists(os.environ["FFPROBE_PATH"]):
        AudioSegment.ffprobe = os.environ["FFPROBE_PATH"]
    elif os.path.exists("/usr/bin/ffprobe"):
        AudioSegment.ffprobe = "/usr/bin/ffprobe"
    
    logger.info(f"pydub configured with: converter={AudioSegment.converter}, ffprobe={AudioSegment.ffprobe}")

# Run setup on import
setup_ffmpeg()

def save_uploaded_file(audio_file):
    """Save an uploaded file to a temporary file on disk."""
    try:
        # Determine file extension
        name = getattr(audio_file, 'name', 'audio_file')
        file_extension = os.path.splitext(name)[1] if '.' in name else '.wav'
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            temp_path = temp_file.name
            
            # Read content from the file
            if hasattr(audio_file, 'read'):
                # If it's a file-like object
                audio_file.seek(0)  # Reset read position
                content = audio_file.read()
            elif hasattr(audio_file, 'getvalue'):
                # If it's a BytesIO object
                content = audio_file.getvalue()
            else:
                # If it's raw binary data
                content = audio_file
                
            # Write to temporary file
            temp_file.write(content)
            
            # Reset read position for potential reuse
            if hasattr(audio_file, 'seek'):
                audio_file.seek(0)
        
        logger.info(f"Saved uploaded file to: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Error saving uploaded file: {str(e)}")
        raise

def process_audio(audio_file):
    """
    Process an audio file for optimal transcription.
    
    Args:
        audio_file: File-like object with audio data
        
    Returns:
        BytesIO: Optimized audio data ready for transcription
    """
    logger.info("Starting audio processing...")
    
    try:
        # Handle different types of input
        if hasattr(audio_file, 'name') and not isinstance(audio_file, BytesIO):
            logger.info(f"Processing file of type: {type(audio_file).__name__}, name: {audio_file.name}")
        else:
            logger.info(f"Processing file of type: {type(audio_file).__name__}")
        
        # Save file temporarily to avoid compatibility issues
        temp_path = save_uploaded_file(audio_file)
        
        try:
            # Process the file with optimize_for_whisper
            processed_path = optimize_for_whisper(temp_path)
            
            # Check that the file exists and has content
            if not os.path.exists(processed_path) or os.path.getsize(processed_path) == 0:
                logger.error(f"Processed file missing or empty: {processed_path}")
                raise RuntimeError("Processed audio file is empty or failed to be created")
            
            # Read the processed file
            with open(processed_path, 'rb') as f:
                processed_audio = BytesIO(f.read())
                processed_audio.name = os.path.basename(processed_path)
            
            # Remove temporary files
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(processed_path) and processed_path != temp_path:
                os.remove(processed_path)
            
            logger.info("Audio processing completed successfully")
            return processed_audio, None
            
        except Exception as e:
            logger.error(f"Error during processing: {str(e)}")
            
            # Fallback: if processing fails, return the original file
            logger.info("Using unprocessed file as fallback")
            with open(temp_path, 'rb') as f:
                original_audio = BytesIO(f.read())
                original_audio.name = os.path.basename(temp_path)
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            return original_audio, str(e)
            
    except Exception as e:
        logger.error(f"Critical error in process_audio: {str(e)}")
        raise RuntimeError(f"Audio processing error: {str(e)}")

def optimize_for_whisper(input_path, max_size_mb=24):
    """
    Optimize an audio file for Whisper API by:
    1. Removing silence
    2. Applying low-pass filter
    3. Converting to mono 16kHz
    4. Compressing to mp3
    
    Args:
        input_path: Path to the input file
        max_size_mb: Maximum file size in MB
        
    Returns:
        str: Path to the optimized file
    """
    try:
        logger.info(f"Optimizing file for Whisper: {input_path}")
        
        # Verify that the file exists
        if not os.path.exists(input_path):
            raise RuntimeError(f"Input file does not exist: {input_path}")
        
        # Verify that AudioSegment is correctly configured
        logger.info(f"AudioSegment.converter = {AudioSegment.converter}")
        logger.info(f"AudioSegment.ffprobe = {getattr(AudioSegment, 'ffprobe', 'Not configured')}")
        
        if not os.path.exists(AudioSegment.converter):
            logger.warning(f"FFmpeg path does not exist: {AudioSegment.converter}")
            if os.path.exists("/usr/bin/ffmpeg"):
                logger.info("Using FFmpeg from /usr/bin/ffmpeg")
                AudioSegment.converter = "/usr/bin/ffmpeg"
            else:
                raise RuntimeError("FFmpeg path is invalid and could not be found in /usr/bin/ffmpeg")
        
        # Read the audio file
        try:
            audio = AudioSegment.from_file(input_path)
        except Exception as e:
            logger.error(f"Could not read audio file: {str(e)}")
            
            # Try different formats
            for format in ['wav', 'mp3', 'm4a', 'ogg']:
                try:
                    logger.info(f"Trying to read as {format}")
                    audio = AudioSegment.from_file(input_path, format=format)
                    break
                except Exception:
                    continue
            else:
                raise RuntimeError(f"Could not read the audio file in any of the common formats: {str(e)}")
        
        logger.info(f"Loaded audio: {len(audio)/1000}s, {audio.channels} channels, {audio.frame_rate}Hz")
        
        # Remove silence
        nonsilent = detect_nonsilent(
            audio, 
            silence_thresh=-45,
            min_silence_len=1000,
            seek_step=100
        )
        
        if not nonsilent:
            logger.info("No non-silent segments found, using entire file")
            processed = audio
        else:
            logger.info(f"Found {len(nonsilent)} non-silent segments")
            processed = AudioSegment.empty()
            for start, end in nonsilent:
                if len(processed) > 0:
                    processed += AudioSegment.silent(duration=100)
                processed += audio[start:end]
            processed = AudioSegment.silent(duration=300) + processed + AudioSegment.silent(duration=300)
            logger.info(f"After silence removal: {len(processed)/1000}s")
        
        # Audio processing
        processed = low_pass_filter(processed, 4000)
        processed = processed.set_channels(1).set_frame_rate(16000)
        logger.info(f"After processing: {len(processed)/1000}s, 1 channel, 16000Hz")
        
        # Create a unique filename for the output file
        output_path = os.path.join(tempfile.gettempdir(), f"processed_audio_{os.getpid()}_{np.random.randint(1000, 9999)}.mp3")
        
        # Ensure temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        
        # Export with compression
        try:
            processed.export(output_path, format="mp3", bitrate="32k")
        except Exception as e:
            logger.error(f"Error during export: {str(e)}")
            
            # Try with a lower bitrate
            try:
                logger.info("Trying with lower bitrate (16k)")
                processed.export(output_path, format="mp3", bitrate="16k")
            except Exception as e2:
                logger.error(f"Still error during export: {str(e2)}")
                
                # Last resort: export as wav
                wav_path = output_path.replace(".mp3", ".wav")
                logger.info(f"Trying to export as WAV: {wav_path}")
                processed.export(wav_path, format="wav")
                output_path = wav_path
        
        logger.info(f"Exported to: {output_path}")
        
        # Check file size
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"Final file size: {size_mb:.2f} MB")
            
            if size_mb > max_size_mb:
                logger.warning(f"Warning: File size ({size_mb:.2f} MB) exceeds limit of {max_size_mb} MB")
        else:
            logger.error(f"Output file does not exist: {output_path}")
            raise RuntimeError(f"Output file could not be created: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Optimization error: {str(e)}")
        raise RuntimeError(f"Optimization error: {str(e)}")