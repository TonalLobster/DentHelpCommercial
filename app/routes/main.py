"""
Main routes for the DentalScribe application.
"""
import os
import json
import tempfile
import datetime
from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm

from app.services.audio_processor import process_audio
from app.services.transcription_service import transcribe_audio
from app.services.summary_service import generate_summary
from app.models.transcription import Transcription
from app import db

main = Blueprint('main', __name__)

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'ogg'}
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

@main.route('/transcribe', methods=['GET', 'POST'])
@login_required
def transcribe():
    """Page for creating new transcriptions."""
    # Create a simple form for CSRF protection
    form = FlaskForm()
    
    if request.method == 'POST':
        # Add these debugging lines
        current_app.logger.info("POST request received for transcription")
        current_app.logger.info(f"Files in request: {list(request.files.keys())}")
        current_app.logger.info(f"Form data: {list(request.form.keys())}")
        current_app.logger.info(f"Content type: {request.headers.get('Content-Type', 'Not provided')}")
        
        # Check if the post request has the file part
        if 'audio' not in request.files:
            current_app.logger.warning("No file in request")
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['audio']
        current_app.logger.info(f"Fil mottagen: {file.filename}")
        
        # If user does not select file, browser also submit an empty part without filename
        if file.filename == '':
            current_app.logger.warning("Filnamn är tomt")
            flash('Ingen fil vald', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            try:
                current_app.logger.info("Börjar bearbeta ljudfil...")
                
                # Process the audio file
                processed_audio, processing_error = process_audio(file)
                
                if processing_error:
                    current_app.logger.warning(f"Varning vid ljudbearbetning: {processing_error}")
                    flash(f'Varning vid ljudbearbetning: {processing_error}', 'warning')
                    # Continue anyway
                
                # Transcribe the audio
                current_app.logger.info("Startar transkribering med OpenAI...")
                transcription_text = transcribe_audio(processed_audio)
                current_app.logger.info(f"Transkription slutförd, längd: {len(transcription_text)} tecken")
                
                # Generate summary
                current_app.logger.info("Genererar sammanfattning...")
                summary_dict = generate_summary(transcription_text)
                current_app.logger.info("Sammanfattning genererad")
                
                # Create new transcription record
                title = request.form.get('title')
                if not title or title.strip() == '':
                    title = 'Transkription ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
                    
                current_app.logger.info(f"Skapar transkriptionspost med titel: {title}")
                new_transcription = Transcription(
                    title=title,
                    user_id=current_user.id,
                    transcription_text=transcription_text,
                    summary=json.dumps(summary_dict, ensure_ascii=False)
                )
                
                # Save to database
                current_app.logger.info("Sparar till databas...")
                db.session.add(new_transcription)
                db.session.commit()
                current_app.logger.info(f"Transkription sparad med ID: {new_transcription.id}")
                
                flash('Transkription skapad framgångsrikt!', 'success')
                return redirect(url_for('main.view_transcription', id=new_transcription.id))
                
            except ValueError as ve:
                current_app.logger.error(f"Valideringsfel: {str(ve)}")
                flash(f'Valideringsfel: {str(ve)}', 'error')
                return redirect(request.url)
                
            except RuntimeError as re:
                current_app.logger.error(f"Körningsfel: {str(re)}")
                flash(f'Körningsfel: {str(re)}', 'error')
                return redirect(request.url)
                
            except Exception as e:
                current_app.logger.error(f"Oväntat fel vid transkribering: {str(e)}", exc_info=True)
                flash(f'Ett oväntat fel inträffade: {str(e)}', 'error')
                return redirect(request.url)
        else:
            current_app.logger.warning(f"Otillåten filtyp: {file.filename}")
            flash('Filtypen är inte tillåten. Vänligen ladda upp WAV, MP3, M4A eller OGG.', 'error')
            return redirect(request.url)
    
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