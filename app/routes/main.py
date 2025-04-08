"""
Main routes for the DentalScribe application.
"""
import os
import json
import base64
import tempfile
import datetime
from io import BytesIO
from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from app.forms import TranscriptionForm  # Import your form
from app.services.audio_processor import process_audio
from app.services.transcription_service import transcribe_audio
from app.services.summary_service import generate_summary
from app.models.transcription import Transcription
from app import db

main = Blueprint('main', __name__)

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'ogg', 'webm', 'mp4'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main.route('/')
def index():
    """Landing page."""
    return render_template('main/index.html')

@main.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing transcription history."""
    # Get user's transcriptions, ordered by most recent first
    transcriptions = Transcription.query.filter_by(user_id=current_user.id).order_by(Transcription.created_at.desc()).all()
    return render_template('main/dashboard.html', transcriptions=transcriptions)

# Update this part of your transcribe route in app/routes/main.py

@main.route('/transcribe', methods=['GET', 'POST'])
@login_required
def transcribe():
    """Page for creating new transcriptions."""
    # Create form for CSRF protection
    form = FlaskForm()
    
    if request.method == 'POST':
        current_app.logger.info("POST request received for transcription")
        current_app.logger.info(f"Form data keys: {list(request.form.keys())}")
        current_app.logger.info(f"Files in request: {list(request.files.keys())}")
        
        # Case 1: Audio recording from browser (as base64 data)
        if 'audio-blob' in request.form and request.form['audio-blob']:
            current_app.logger.info("Processing recorded audio (base64 data)")
            try:
                # Extract the actual base64 content after the data URL header
                audio_data = request.form['audio-blob']
                if ',' in audio_data:
                    header, encoded = audio_data.split(",", 1)
                    current_app.logger.info(f"Audio data format: {header}")
                else:
                    encoded = audio_data
                
                # Get file size estimate
                estimated_size_kb = len(encoded) * 3 / 4 / 1024  # base64 encoding adds ~33% overhead
                current_app.logger.info(f"Estimated decoded size: {estimated_size_kb:.2f} KB")
                
                if estimated_size_kb > 100 * 1024:  # > 100MB
                    flash('Inspelningen är för stor. Maximal filstorlek är 100MB.', 'error')
                    return redirect(request.url)
                
                # Decode the base64 data to binary
                try:
                    audio_bytes = base64.b64decode(encoded)
                    current_app.logger.info(f"Successfully decoded base64 data, size: {len(audio_bytes) // 1024} KB")
                except Exception as e:
                    current_app.logger.error(f"Error decoding base64: {str(e)}")
                    flash('Kunde inte avkoda ljuddata. Försök igen eller ladda upp en fil.', 'error')
                    return redirect(request.url)
                
                # Save to temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
                temp_file.write(audio_bytes)
                temp_file.close()
                current_app.logger.info(f"Saved temporary file: {temp_file.name}, size: {os.path.getsize(temp_file.name) // 1024} KB")
                
                # Process the audio from the file
                try:
                    with open(temp_file.name, 'rb') as f:
                        file_like = BytesIO(f.read())
                        file_like.name = os.path.basename(temp_file.name)
                        
                        processed_audio, processing_error = process_audio(file_like)
                        
                        if processing_error:
                            current_app.logger.warning(f"Audio processing warning: {processing_error}")
                            flash(f'Varning vid ljudbearbetning: {processing_error}', 'warning')
                except Exception as e:
                    current_app.logger.error(f"Error processing audio: {str(e)}")
                    flash(f'Fel vid ljudbearbetning: {str(e)}', 'error')
                    # Try to continue with original file
                    with open(temp_file.name, 'rb') as f:
                        processed_audio = BytesIO(f.read())
                        processed_audio.name = os.path.basename(temp_file.name)
                
                # Continue with transcription
                try:
                    current_app.logger.info("Starting transcription")
                    transcription_text = transcribe_audio(processed_audio)
                    current_app.logger.info(f"Transcription complete, length: {len(transcription_text)} characters")
                except Exception as e:
                    current_app.logger.error(f"Transcription error: {str(e)}")
                    flash(f'Fel vid transkribering: {str(e)}', 'error')
                    
                    # Clean up temporary file
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                        
                    return redirect(request.url)
                
                # Generate summary
                try:
                    current_app.logger.info("Generating summary")
                    summary_dict = generate_summary(transcription_text)
                    current_app.logger.info("Summary generated")
                except Exception as e:
                    current_app.logger.error(f"Summary generation error: {str(e)}")
                    flash(f'Fel vid sammanfattningsgenerering: {str(e)}', 'error')
                    summary_dict = {"error": f"Kunde inte generera sammanfattning: {str(e)}"}
                
                # Create new transcription record
                title = request.form.get('recording-title')
                if not title or title.strip() == '':
                    title = 'Inspelning ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
                
                current_app.logger.info(f"Creating transcription with title: {title}")
                new_transcription = Transcription(
                    title=title,
                    user_id=current_user.id,
                    transcription_text=transcription_text,
                    summary=json.dumps(summary_dict, ensure_ascii=False)
                )
                
                # Save to database
                db.session.add(new_transcription)
                db.session.commit()
                current_app.logger.info(f"Transcription saved with ID: {new_transcription.id}")
                
                # Clean up temporary file
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
                
                flash('Transkription skapad framgångsrikt!', 'success')
                return redirect(url_for('main.view_transcription', id=new_transcription.id))
            
            except Exception as e:
                current_app.logger.error(f"Unexpected error with recorded audio: {str(e)}", exc_info=True)
                flash(f'Ett oväntat fel inträffade: {str(e)}', 'error')
                return redirect(request.url)
        
        # Case 2: File upload
        elif 'audio' in request.files:
            file = request.files['audio']
            current_app.logger.info(f"Received file: {file.filename}")
            
            # Check if file was actually selected
            if file.filename == '':
                current_app.logger.warning("Empty filename")
                flash('Ingen fil vald', 'error')
                return redirect(request.url)
            
            # Check file size before processing
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Reset file pointer
            
            current_app.logger.info(f"File size: {file_size // 1024} KB")
            
            if file_size > 100 * 1024 * 1024:  # 100MB limit
                flash('Filen är för stor. Maximal filstorlek är 100MB.', 'error')
                return redirect(request.url)
            
            # Check if file type is allowed
            allowed_extensions = {'wav', 'mp3', 'ogg', 'm4a', 'webm'}
            if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
                flash('Filtypen är inte tillåten. Vänligen ladda upp WAV, MP3, OGG, M4A eller WEBM.', 'error')
                return redirect(request.url)
            
            try:
                # Process the audio file
                current_app.logger.info("Processing audio file")
                processed_audio, processing_error = process_audio(file)
                
                if processing_error:
                    current_app.logger.warning(f"Audio processing warning: {processing_error}")
                    flash(f'Varning vid ljudbearbetning: {processing_error}', 'warning')
                
                # Transcribe the audio
                current_app.logger.info("Starting transcription")
                transcription_text = transcribe_audio(processed_audio)
                current_app.logger.info(f"Transcription complete, length: {len(transcription_text)} characters")
                
                # Generate summary
                current_app.logger.info("Generating summary")
                summary_dict = generate_summary(transcription_text)
                current_app.logger.info("Summary generated")
                
                # Create new transcription record
                title = request.form.get('title')
                if not title or title.strip() == '':
                    title = 'Uppladdning ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
                
                current_app.logger.info(f"Creating transcription with title: {title}")
                new_transcription = Transcription(
                    title=title,
                    user_id=current_user.id,
                    transcription_text=transcription_text,
                    summary=json.dumps(summary_dict, ensure_ascii=False)
                )
                
                # Save to database
                db.session.add(new_transcription)
                db.session.commit()
                current_app.logger.info(f"Transcription saved with ID: {new_transcription.id}")
                
                flash('Transkription skapad framgångsrikt!', 'success')
                return redirect(url_for('main.view_transcription', id=new_transcription.id))
            
            except Exception as e:
                current_app.logger.error(f"Error during file upload processing: {str(e)}", exc_info=True)
                flash(f'Ett fel inträffade: {str(e)}', 'error')
                return redirect(request.url)
        
        else:
            flash('Ingen ljudfil eller inspelning hittades i förfrågan', 'error')
            return redirect(request.url)
    
    # GET request - display the form
    return render_template('main/transcribe.html', form=form)

@main.route('/transcriptions/<int:id>')
@login_required
def view_transcription(id):
    """View a single transcription."""
    transcription = Transcription.query.get_or_404(id)
    
    # Security check: ensure user owns this transcription
    if transcription.user_id != current_user.id:
        flash('You do not have permission to view this transcription.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Parse summary JSON
    try:
        summary = json.loads(transcription.summary)
    except:
        summary = {
            "anamnes": "Error parsing summary",
            "status": "Error parsing summary",
            "diagnos": "Error parsing summary",
            "åtgärd": "Error parsing summary",
            "behandlingsplan": "Error parsing summary",
            "kommunikation": "Error parsing summary"
        }
    
    return render_template('main/view_transcription.html', 
                          transcription=transcription, 
                          summary=summary)

@main.route('/api/transcribe', methods=['POST'])
@login_required
def api_transcribe():
    """API endpoint for transcribing audio."""
    try:
        # Check if file was uploaded
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file sent"}), 400
        
        audio_file = request.files['audio']
        if not audio_file.filename:
            return jsonify({"error": "File without name sent"}), 400
        
        # Check file size
        if request.content_length and request.content_length > 100 * 1024 * 1024:
            return jsonify({"error": "File is too large. Maximum file size is 100MB."}), 413
        
        # Save original audio temporarily for debugging
        temp_original = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        audio_file.save(temp_original.name)
        audio_file.seek(0)  # Reset file pointer
        
        # Process the audio file
        try:
            processed_audio, processing_error = process_audio(audio_file)
            
            if processing_error:
                current_app.logger.warning(f"Audio processing warning: {processing_error}")
                # Continue anyway
                
        except Exception as e:
            current_app.logger.error(f"Error during audio processing: {str(e)}")
            # Fallback: use original file if processing fails
            with open(temp_original.name, 'rb') as f:
                processed_audio = f
                audio_file = f
        
        # Transcribe the audio file
        try:
            transcription_text = transcribe_audio(processed_audio)
        except Exception as e:
            current_app.logger.error(f"Error during transcription: {str(e)}")
            # Try again with original file
            with open(temp_original.name, 'rb') as f:
                transcription_text = transcribe_audio(f)
        
        # Generate summary
        summary_dict = generate_summary(transcription_text)
        
        # Create new transcription record if requested
        if request.form.get('save', 'true').lower() == 'true':
            new_transcription = Transcription(
                title=request.form.get('title', 'API Transcription'),
                user_id=current_user.id,
                transcription_text=transcription_text,
                summary=json.dumps(summary_dict, ensure_ascii=False)
            )
            
            db.session.add(new_transcription)
            db.session.commit()
            
            # Add transcription ID to response
            summary_dict['transcription_id'] = new_transcription.id
        
        # Remove temporary file
        if os.path.exists(temp_original.name):
            os.unlink(temp_original.name)
        
        # Add transcription text to response
        response_data = {
            'summary': summary_dict,
            'transcription': transcription_text
        }
        
        return jsonify(response_data)
        
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except RuntimeError as re:
        return jsonify({"error": str(re)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500