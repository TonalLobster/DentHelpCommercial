"""
Main routes for the DentalScribe application.
"""
import os
import json
import tempfile
import datetime
import base64
from io import BytesIO
from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from app.models.transcription import Transcription
from app import db
from app.tasks.transcription_tasks import transcribe_audio_task

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

@main.route('/transcribe', methods=['GET', 'POST'])
@login_required
def transcribe():
    """Page for creating new transcriptions using Celery for async processing."""
    # Create a simple form for CSRF protection
    form = FlaskForm()
    
    if request.method == 'POST':
        # Log request details
        current_app.logger.info("POST request received for transcription")
        current_app.logger.info(f"Files in request: {list(request.files.keys())}")
        current_app.logger.info(f"Form data: {list(request.form.keys())}")
        current_app.logger.info(f"Content type: {request.headers.get('Content-Type', 'Not provided')}")
        
        # Check for audio-blob (from recorder) or audio file
        audio_data = None
        file_from_recorder = False
        
        if 'audio-blob' in request.form and request.form['audio-blob']:
            # Handle recorded audio blob
            current_app.logger.info("Audio blob found in form data")
            audio_data = request.form['audio-blob']
            file_from_recorder = True
        elif 'audio' in request.files:
            # Handle uploaded file
            file = request.files['audio']
            current_app.logger.info(f"File received: {file.filename}")
            
            if file.filename == '':
                current_app.logger.warning("File name is empty")
                flash('Ingen fil vald', 'error')
                return redirect(request.url)
                
            if not allowed_file(file.filename):
                current_app.logger.warning(f"Invalid file type: {file.filename}")
                flash('Filtypen är inte tillåten. Vänligen ladda upp WAV, MP3, M4A, OGG, WEBM eller MP4.', 'error')
                return redirect(request.url)
                
            # Save file to temp location and get path
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
            file.save(temp_file.name)
            audio_data = temp_file.name
        else:
            current_app.logger.warning("No audio data in request")
            flash('Ingen ljuddata hittades', 'error')
            return redirect(request.url)
            
        # Get title from form
        title = request.form.get('title')
        if not title or title.strip() == '':
            title = 'Transkription ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            
        # Prepare form data for Celery task
        form_data = {
            'title': title,
            'recorder': file_from_recorder
        }
        
        # Submit task to Celery
        try:
            current_app.logger.info("Submitting task to Celery")
            task = transcribe_audio_task.delay(audio_data, form_data, current_user.id)
            
            # Store task ID in session for status checking
            session['transcription_task_id'] = task.id
            session['task_submitted_time'] = datetime.datetime.now().isoformat()
            
            flash('Transkription skickad för bearbetning. Du kommer att meddelas när den är klar.', 'info')
            return redirect(url_for('celery.task_status_page', task_id=task.id))
            
        except Exception as e:
            current_app.logger.error(f"Error submitting task to Celery: {str(e)}", exc_info=True)
            flash(f'Fel vid skickande av transkriptionsuppgift: {str(e)}', 'error')
            
            # If we saved a temporary file, clean it up
            if not file_from_recorder and 'temp_file' in locals():
                try:
                    os.unlink(temp_file.name)
                except Exception as file_error:
                    current_app.logger.error(f"Could not delete temp file: {str(file_error)}")
                    
            return redirect(request.url)
    
    return render_template('main/transcribe.html', form=form)

@main.route('/transcriptions/<int:id>')
@login_required
def view_transcription(id):
    """View a single transcription."""
    transcription = Transcription.query.get_or_404(id)
    
    # Security check: ensure user owns this transcription
    if transcription.user_id != current_user.id:
        flash('Du har inte behörighet att visa denna transkription.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Parse summary JSON
    try:
        summary = json.loads(transcription.summary)
    except:
        summary = {
            "anamnes": "Fel vid tolkning av sammanfattningen",
            "status": "Fel vid tolkning av sammanfattningen",
            "diagnos": "Fel vid tolkning av sammanfattningen",
            "åtgärd": "Fel vid tolkning av sammanfattningen",
            "behandlingsplan": "Fel vid tolkning av sammanfattningen",
            "kommunikation": "Fel vid tolkning av sammanfattningen"
        }
    
    return render_template('main/view_transcription.html', 
                          transcription=transcription, 
                          summary=summary)

@main.route('/api/transcribe', methods=['POST'])
@login_required
def api_transcribe():
    """API endpoint for transcribing audio using Celery."""
    try:
        # Check if file was uploaded
        if 'audio' not in request.files:
            return jsonify({"error": "Ingen ljudfil skickad"}), 400
        
        audio_file = request.files['audio']
        if not audio_file.filename:
            return jsonify({"error": "Fil utan namn skickad"}), 400
        
        # Check file size
        if request.content_length and request.content_length > 100 * 1024 * 1024:
            return jsonify({"error": "Filen är för stor. Maximal filstorlek är 100 MB."}), 413
        
        # Save original audio temporarily
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_file.filename)[1])
        audio_file.save(temp_file.name)
        audio_file.seek(0)  # Reset file pointer
        
        # Get form data
        form_data = {
            'title': request.form.get('title', 'API Transkription'),
            'save': request.form.get('save', 'true').lower() == 'true',
            'patient_id': request.form.get('patient_id', None)
        }
        
        # Submit task to Celery
        task = transcribe_audio_task.delay(temp_file.name, form_data, current_user.id)
        
        # Return task ID
        return jsonify({
            'status': 'success',
            'message': 'Transkription skickad för bearbetning',
            'task_id': task.id
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in API transcribe: {str(e)}", exc_info=True)
        return jsonify({"error": f"Ett oväntat fel inträffade: {str(e)}"}), 500