import os
import tempfile
import logging
from io import BytesIO
import numpy as np
import librosa
import soundfile as sf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("audio_processor")

def save_uploaded_file(audio_file):
    """Saves an uploaded file to a temporary file on disk."""
    try:
        # Determine file extension
        name = getattr(audio_file, 'name', 'audio_file')
        file_extension = os.path.splitext(name)[1] if '.' in name else '.wav'
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            temp_path = temp_file.name
            
            # Read content from file
            if hasattr(audio_file, 'read'):
                audio_file.seek(0)  # Reset read position
                content = audio_file.read()
            elif hasattr(audio_file, 'getvalue'):
                content = audio_file.getvalue()
            else:
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
    Processes an audio file for optimal transcription using librosa.
    
    Args:
        audio_file: File-like object with audio data
        
    Returns:
        BytesIO: Optimized audio data ready for transcription
    """
    logger.info("Starting audio processing...")
    
    try:
        # Handle different types of input
        if hasattr(audio_file, 'name'):
            logger.info(f"Processing file of type: {type(audio_file).__name__}, name: {audio_file.name}")
        else:
            logger.info(f"Processing file of type: {type(audio_file).__name__}")
        
        # Save file temporarily to avoid compatibility issues
        temp_path = save_uploaded_file(audio_file)
        
        try:
            # Process the file with optimize_for_whisper
            processed_path = optimize_for_whisper(temp_path)
            
            # Check that file exists and has content
            if not os.path.exists(processed_path) or os.path.getsize(processed_path) == 0:
                logger.error(f"Processed file is missing or empty: {processed_path}")
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
            
            # Fallback: if processing fails, return original file
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
    Optimizes an audio file for Whisper API by:
    1. Removing silence
    2. Normalizing audio
    3. Converting to mono 16kHz
    4. Exporting as mp3
    
    Args:
        input_path: Path to the input file
        max_size_mb: Maximum file size in MB
        
    Returns:
        str: Path to the optimized file
    """
    try:
        logger.info(f"Optimizing file for Whisper: {input_path}")
        
        # Verify file exists
        if not os.path.exists(input_path):
            raise RuntimeError(f"Input file does not exist: {input_path}")
        
        # Load the audio file
        try:
            y, sr = librosa.load(input_path, sr=None)
        except Exception as e:
            logger.error(f"Could not load audio file: {str(e)}")
            raise RuntimeError(f"Could not load audio file: {str(e)}")
        
        logger.info(f"Loaded audio: {len(y)/sr}s, {sr}Hz")
        
        # Remove silence
        non_silent = librosa.effects.split(y, top_db=30)
        
        if len(non_silent) == 0:
            logger.info("No non-silent segments found, using whole file")
            processed = y
        else:
            logger.info(f"Found {len(non_silent)} non-silent segments")
            processed = np.concatenate([y[start:end] for start, end in non_silent])
            
            # Add a bit of silence at beginning and end
            silence_samples = int(0.3 * sr)
            silence = np.zeros(silence_samples)
            processed = np.concatenate([silence, processed, silence])
            
            logger.info(f"After silence removal: {len(processed)/sr}s")
        
        # Normalize audio
        processed = librosa.util.normalize(processed)
        
        # Resample to 16kHz mono
        if sr != 16000:
            processed = librosa.resample(processed, orig_sr=sr, target_sr=16000)
            sr = 16000
            logger.info(f"Resampled to: {len(processed)/sr}s, 16000Hz")
        
        # Create a unique filename for the output file
        output_path = os.path.join(tempfile.gettempdir(), f"processed_audio_{os.getpid()}_{np.random.randint(1000, 9999)}.mp3")
        
        # Ensure temp directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        
        # Export with compression
        sf.write(output_path, processed, sr, format='mp3', subtype='VORBIS')
        
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

# Test module when run directly
if __name__ == "__main__":
    logging.info("Testing audio_processor...")
    try:
        # Create a test file with silence
        test_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        
        # Generate silence (zeros) and save as WAV
        import soundfile as sf
        import numpy as np
        
        sample_rate = 16000
        duration = 1  # seconds
        samples = np.zeros(int(sample_rate * duration))
        sf.write(test_path, samples, sample_rate)
        
        # Test process_audio
        with open(test_path, "rb") as f:
            test_bytes = BytesIO(f.read())
            test_bytes.name = "test_audio.wav"
            
            result, error = process_audio(test_bytes)
            if error:
                logging.error(f"Test failed: {error}")
            else:
                logging.info("Test succeeded!")
        
        # Clean up
        os.remove(test_path)
        
    except Exception as e:
        logging.error(f"Test error: {str(e)}")