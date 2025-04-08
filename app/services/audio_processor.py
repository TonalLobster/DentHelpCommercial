"""
Enhanced audio processing functions for app/services/audio_processor.py
"""
import os
import tempfile
import logging
from io import BytesIO
import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from pydub.effects import low_pass_filter, normalize

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
        file_extension = os.path.splitext(name)[1].lower() if '.' in name else '.wav'
        
        # Map common mime types to extensions
        if not file_extension or file_extension == '.':
            mime_type = getattr(audio_file, 'content_type', '')
            ext_map = {
                'audio/mp3': '.mp3',
                'audio/mpeg': '.mp3',
                'audio/ogg': '.ogg',
                'audio/wav': '.wav',
                'audio/wave': '.wav',
                'audio/x-wav': '.wav',
                'audio/webm': '.webm',
                'audio/m4a': '.m4a',
                'audio/mp4': '.m4a',
                'audio/x-m4a': '.m4a'
            }
            file_extension = ext_map.get(mime_type, '.wav')
        
        logger.info(f"Using file extension: {file_extension}")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            temp_path = temp_file.name
            
            # Read content from the file
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
        
        # Log file size
        file_size_mb = os.path.getsize(temp_path) / (1024 * 1024)
        logger.info(f"Saved uploaded file to: {temp_path} ({file_size_mb:.2f} MB)")
        return temp_path
    except Exception as e:
        logger.error(f"Error saving uploaded file: {str(e)}")
        raise

def process_audio(audio_file):
    """
    Processes an audio file for optimal transcription.
    
    Args:
        audio_file: File-like object with audio data
        
    Returns:
        BytesIO: Optimized audio data ready for transcription
        str: Error message if any (or None)
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
            # Get file size in MB
            file_size_mb = os.path.getsize(temp_path) / (1024 * 1024)
            logger.info(f"Original file size: {file_size_mb:.2f} MB")
            
            # Optimize audio for Whisper API (size, format, etc.)
            try:
                processed_path = optimize_for_whisper(temp_path)
                
                # Check that file exists and has content
                if not os.path.exists(processed_path) or os.path.getsize(processed_path) == 0:
                    logger.error(f"Processed file is missing or empty: {processed_path}")
                    raise RuntimeError("Processed audio file is empty or failed to be created")
                
                processed_size_mb = os.path.getsize(processed_path) / (1024 * 1024)
                logger.info(f"Processed file size: {processed_size_mb:.2f} MB")
                
                reduction_pct = ((file_size_mb - processed_size_mb) / file_size_mb) * 100 if file_size_mb > 0 else 0
                logger.info(f"Size reduction: {reduction_pct:.1f}%")
                
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
            logger.error(f"Error in process_audio: {str(e)}")
            
            # Last resort fallback
            if os.path.exists(temp_path):
                with open(temp_path, 'rb') as f:
                    fallback_audio = BytesIO(f.read())
                    fallback_audio.name = os.path.basename(temp_path)
                os.remove(temp_path)
                return fallback_audio, f"Fallback mode due to error: {str(e)}"
            else:
                raise
            
    except Exception as e:
        logger.error(f"Critical error in process_audio: {str(e)}")
        raise RuntimeError(f"Audio processing error: {str(e)}")

def optimize_for_whisper(input_path, max_size_mb=24):
    """
    Optimizes an audio file for Whisper API by:
    1. Identifying and preserving speech segments
    2. Removing silence
    3. Normalizing the audio
    4. Converting to mono 16kHz
    5. Compressing to MP3 with lower bitrate for longer recordings
    
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
            raise RuntimeError(f"Input file doesn't exist: {input_path}")
        
        # Load the audio file
        try:
            audio = AudioSegment.from_file(input_path)
        except Exception as e:
            logger.error(f"Couldn't load audio file: {str(e)}")
            
            # Try with different formats
            for format in ['wav', 'mp3', 'm4a', 'ogg', 'webm']:
                try:
                    logger.info(f"Trying to load as {format}")
                    audio = AudioSegment.from_file(input_path, format=format)
                    break
                except Exception:
                    continue
            else:
                raise RuntimeError(f"Couldn't load audio file in any common format: {str(e)}")
        
        # Log original audio information
        original_duration = len(audio) / 1000
        logger.info(f"Loaded audio: {original_duration:.2f}s, {audio.channels} channels, {audio.frame_rate}Hz")
        
        # For very long recordings (over 30 minutes), use more aggressive optimization
        if original_duration > 1800:  # 30 minutes
            logger.info("Long recording detected, using aggressive optimization")
            silence_thresh = -40  # Less sensitive silence detection
            min_silence_len = 2000  # Longer minimum silence to preserve more speech
            bitrate = "16k"  # Lower bitrate
        else:
            silence_thresh = -45  # Default silence threshold
            min_silence_len = 1000  # Default minimum silence length
            bitrate = "32k"  # Default bitrate
            
        # Remove silence, preserve speech segments
        nonsilent = detect_nonsilent(
            audio, 
            silence_thresh=silence_thresh,
            min_silence_len=min_silence_len,
            seek_step=100
        )
        
        if len(nonsilent) == 0:
            logger.warning("No non-silent segments found, using entire file")
            processed = audio
        else:
            # Concatenate only non-silent segments
            processed = AudioSegment.empty()
            for start, end in nonsilent:
                if len(processed) > 0:
                    processed += AudioSegment.silent(duration=100)
                processed += audio[start:end]
            
            # Add small silence buffers
            processed = AudioSegment.silent(duration=300) + processed + AudioSegment.silent(duration=300)
        
        # Calculate actual speech duration
        speech_duration = len(processed) / 1000
        logger.info(f"Preserved speech duration: {speech_duration:.2f}s")
        
        # Normalize audio (adjust volume)
        try:
            processed = normalize(processed)
            logger.info("Audio normalized")
        except Exception as e:
            logger.warning(f"Could not normalize audio: {str(e)}")
        
        # Downmix to mono and set sample rate to 16kHz
        processed = processed.set_channels(1).set_frame_rate(16000)
        
        # Apply light compression for clearer speech
        processed = low_pass_filter(processed, 4000)
        
        # Create unique filename for output
        output_path = os.path.join(
            tempfile.gettempdir(), 
            f"processed_audio_{os.getpid()}_{np.random.randint(1000, 9999)}.mp3"
        )
        
        # Ensure temp directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        
        # Determine bitrate based on duration for better compression of longer files
        if speech_duration > 7200:  # > 2 hours
            bitrate = "8k"  # Very low bitrate for extremely long recordings
        elif speech_duration > 3600:  # > 1 hour
            bitrate = "16k"  # Low bitrate for long recordings
        
        # Export with compression and better error handling
        try:
            logger.info(f"Trying to export with {bitrate} bitrate")
            processed.export(output_path, format="mp3", bitrate=bitrate)
        except Exception as e:
            logger.error(f"Error exporting with {bitrate} bitrate: {str(e)}")
            
            # Try with a lower bitrate
            try:
                logger.info("Trying with lower bitrate (8k)")
                processed.export(output_path, format="mp3", bitrate="8k")
            except Exception as e2:
                logger.error(f"Error exporting with 8k bitrate: {str(e2)}")
                
                # Last resort: export as wav
                wav_path = output_path.replace(".mp3", ".wav")
                logger.info(f"Trying to export as WAV: {wav_path}")
                processed.export(wav_path, format="wav")
                output_path = wav_path
        
        # Check file size
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"Final file size: {size_mb:.2f} MB")
            
            # If file is still too large, try more aggressive compression
            if size_mb > max_size_mb and output_path.endswith('.mp3'):
                logger.warning(f"Warning: File size ({size_mb:.2f} MB) exceeds limit of {max_size_mb} MB")
                logger.info("Trying with more aggressive compression (mono, 8kHz, 8k bitrate)")
                
                # Convert to mono and lower sampling rate
                try:
                    lower_rate = processed.set_frame_rate(8000)
                    lower_rate_path = output_path.replace(".mp3", "_low.mp3")
                    lower_rate.export(lower_rate_path, format="mp3", bitrate="8k")
                    
                    # If export succeeds, use the lower quality version
                    if os.path.exists(lower_rate_path) and os.path.getsize(lower_rate_path) > 0:
                        # Remove the original file
                        os.remove(output_path)
                        output_path = lower_rate_path
                        size_mb = os.path.getsize(output_path) / (1024 * 1024)
                        logger.info(f"New file size after aggressive compression: {size_mb:.2f} MB")
                except Exception as e:
                    logger.error(f"Couldn't perform aggressive compression: {str(e)}")
        else:
            logger.error(f"Output file doesn't exist: {output_path}")
            raise RuntimeError(f"Output file couldn't be created: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Optimization error: {str(e)}")
        raise RuntimeError(f"Optimization error: {str(e)}")
    
def optimize_for_large_files(input_path, max_size_mb=24):
    
    try:
        logger.info(f"Starting optimization for large file: {input_path}")
        
        # Try to load the audio with low memory usage
        file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        logger.info(f"Input file size: {file_size_mb:.2f} MB")
        
        # For very large files, we'll use a more memory-efficient approach
        if file_size_mb > 500:  # More than 500MB
            logger.info("Very large file detected, using chunked processing")
            return process_large_file_in_chunks(input_path, max_size_mb)
        
        # Standard approach for large but manageable files
        audio = AudioSegment.from_file(input_path)
        
        # Log original details
        original_duration = len(audio) / 1000
        logger.info(f"Loaded audio: {original_duration:.2f}s, {audio.channels} channels, {audio.frame_rate}Hz")
        
        # Aggressive silence removal
        nonsilent = detect_nonsilent(
            audio, 
            silence_thresh=-38,        # Less sensitive
            min_silence_len=2500,      # Longer silence periods detected
            seek_step=200              # Faster but less precise analysis
        )
        
        if len(nonsilent) == 0:
            logger.warning("No non-silent segments found, using entire file")
            processed = audio
        else:
            # Concatenate only non-silent segments
            processed = AudioSegment.empty()
            for start, end in nonsilent:
                processed += audio[start:end]
            
            # Add minimal silence buffer
            processed = AudioSegment.silent(duration=100) + processed + AudioSegment.silent(duration=100)
        
        # Calculate processing stats
        speech_duration = len(processed) / 1000
        reduction_pct = 100 - (speech_duration / original_duration * 100)
        logger.info(f"Speech duration: {speech_duration:.2f}s (reduced by {reduction_pct:.1f}%)")
        
        # Aggressive compression settings
        processed = processed.set_channels(1)           # Mono
        processed = processed.set_frame_rate(16000)     # 16kHz
        processed = low_pass_filter(processed, 3500)    # More aggressive low-pass
        
        # Create output path
        output_path = os.path.join(
            tempfile.gettempdir(), 
            f"large_audio_{os.getpid()}_{np.random.randint(1000, 9999)}.mp3"
        )
        
        # Export with low bitrate
        bitrate = "8k"  # Very low bitrate for large files
        try:
            logger.info(f"Exporting with {bitrate} bitrate")
            processed.export(output_path, format="mp3", bitrate=bitrate)
        except Exception as e:
            logger.error(f"Error with bitrate {bitrate}: {str(e)}")
            
            # Alternative format as fallback
            try:
                logger.info("Trying with OGG format at low quality")
                ogg_path = output_path.replace(".mp3", ".ogg")
                processed.export(ogg_path, format="ogg", parameters=["-q:a", "1"])
                output_path = ogg_path
            except Exception as e2:
                logger.error(f"Error with OGG export: {str(e2)}")
                
                # Last resort: simple WAV conversion
                logger.info("Falling back to WAV format")
                wav_path = output_path.replace(".mp3", ".wav")
                processed.export(wav_path, format="wav")
                output_path = wav_path
        
        # Check final size
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"Final file size: {size_mb:.2f} MB")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Large file optimization error: {str(e)}")
        raise RuntimeError(f"Large file optimization error: {str(e)}")

def process_large_file_in_chunks(input_path, max_size_mb=24):
    """
    Process very large audio files in chunks to avoid memory issues.
    
    Args:
        input_path: Path to the input file
        max_size_mb: Maximum file size in MB
        
    Returns:
        str: Path to the optimized file
    """
    try:
        logger.info("Starting chunked processing for very large file")
        
        # Create output path
        output_path = os.path.join(
            tempfile.gettempdir(), 
            f"chunked_audio_{os.getpid()}_{np.random.randint(1000, 9999)}.mp3"
        )
        
        # Get file info without loading into memory
        from subprocess import check_output
        try:
            import json
            # Try to use ffprobe to get info
            cmd = [
                'ffprobe', 
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                input_path
            ]
            result = check_output(cmd).decode('utf-8')
            info = json.loads(result)
            duration = float(info['format']['duration'])
            logger.info(f"File duration: {duration:.2f} seconds")
            
            # Process in 10-minute chunks
            chunk_duration = 600  # 10 minutes in seconds
            chunks = int(duration / chunk_duration) + 1
            logger.info(f"Processing in {chunks} chunks")
            
            # Process each chunk and combine
            from pydub import AudioSegment
            combined = AudioSegment.empty()
            
            for i in range(chunks):
                start_time = i * chunk_duration
                end_time = min((i + 1) * chunk_duration, duration)
                
                if end_time <= start_time:
                    break
                    
                logger.info(f"Processing chunk {i+1}/{chunks} ({start_time:.2f}s to {end_time:.2f}s)")
                
                # Extract chunk with ffmpeg
                chunk_path = f"{input_path}.chunk{i}.wav"
                extract_cmd = [
                    'ffmpeg',
                    '-i', input_path,
                    '-ss', str(start_time),
                    '-to', str(end_time),
                    '-ac', '1',         # Mono
                    '-ar', '16000',     # 16kHz
                    '-y',               # Overwrite output
                    chunk_path
                ]
                check_output(extract_cmd)
                
                # Process chunk to remove silence
                try:
                    chunk = AudioSegment.from_file(chunk_path)
                    nonsilent = detect_nonsilent(chunk, silence_thresh=-40, min_silence_len=1000)
                    
                    if nonsilent:
                        processed_chunk = AudioSegment.empty()
                        for start, end in nonsilent:
                            processed_chunk += chunk[start:end]
                    else:
                        processed_chunk = chunk
                        
                    # Add to combined audio
                    combined += processed_chunk
                    
                    # Clean up chunk file
                    os.remove(chunk_path)
                    
                except Exception as e:
                    logger.error(f"Error processing chunk {i}: {str(e)}")
                    # If chunk processing fails, add original chunk to avoid data loss
                    chunk = AudioSegment.from_file(chunk_path)
                    combined += chunk
                    os.remove(chunk_path)
            
            # Export combined audio with low bitrate
            logger.info("Exporting combined audio with low bitrate")
            combined.export(output_path, format="mp3", bitrate="16k")
            
            # Check final size
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"Final combined file size: {size_mb:.2f} MB")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error during chunked processing: {str(e)}")
            
            # Fallback: try direct conversion with ffmpeg
            logger.info("Falling back to direct ffmpeg conversion")
            fallback_path = output_path.replace(".mp3", "_fallback.mp3")
            fallback_cmd = [
                'ffmpeg',
                '-i', input_path,
                '-ac', '1',             # Mono
                '-ar', '16000',         # 16kHz
                '-codec:a', 'libmp3lame',
                '-b:a', '16k',          # Low bitrate
                '-y',                   # Overwrite output
                fallback_path
            ]
            check_output(fallback_cmd)
            
            return fallback_path
            
    except Exception as e:
        logger.error(f"Chunked processing error: {str(e)}")
        
        # Last resort: simple conversion
        try:
            logger.info("Using last resort direct conversion")
            last_resort_path = os.path.join(
                tempfile.gettempdir(), 
                f"last_resort_{os.getpid()}.mp3"
            )
            
            simple_cmd = [
                'ffmpeg',
                '-i', input_path,
                '-ac', '1',
                '-ar', '8000',          # Very low sample rate
                '-codec:a', 'libmp3lame',
                '-b:a', '8k',           # Lowest reasonable bitrate
                '-y',
                last_resort_path
            ]
            check_output(simple_cmd)
            
            return last_resort_path
        except:
            # If all fails, return original path
            logger.error("All optimization attempts failed, returning original file")
            return input_path
    