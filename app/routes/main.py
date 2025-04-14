"""
Main routes for the DentalScribe application.
"""
import os
import json
import tempfile
import datetime
from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from app.services.audio_processor import process_audio
from app.services.transcription_service import transcribe_audio
from app.services.summary_service import generate_summary
from app.models.transcription import Transcription
from app.utils.progress_tracker import register_task, update_task_status, get_task_status
from app import db

main = Blueprint('main', __name__, url_prefix='')

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

@main.route('/transcription/status/<task_id>')
@login_required
def transcription_status(task_id):
    """Show status of a transcription task."""
    from app.celery_worker import celery
    
    task = celery.AsyncResult(task_id)
    
    # Lagra task_id i sessionen också
    session['current_task_id'] = task_id
    
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Din transkription väntar på att bearbetas...'
        }
    elif task.state == 'PROCESSING_AUDIO':
        response = {
            'state': task.state,
            'status': 'Bearbetar ljudfilen...'
        }
    elif task.state == 'TRANSCRIBING':
        response = {
            'state': task.state,
            'status': 'Transkriberar ljudet...'
        }
    elif task.state == 'GENERATING_SUMMARY':
        response = {
            'state': task.state,
            'status': 'Genererar sammanfattning...'
        }
    elif task.state == 'SAVING':
        response = {
            'state': task.state,
            'status': 'Sparar transkription...'
        }
    elif task.state == 'FAILURE':
        # Something went wrong in the background job
        response = {
            'state': task.state,
            'status': 'Ett fel uppstod under bearbetningen.',
            'error': str(task.info)
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'status': 'Transkription slutförd!'
        }
        # If task.info is a dict with a transcription_id, include it in the response
        if isinstance(task.info, dict) and 'transcription_id' in task.info:
            response['transcription_id'] = task.info['transcription_id']
            # Redirect to the transcription page
            return redirect(url_for('main.view_transcription', id=task.info['transcription_id']))
    else:
        # Something unexpected
        response = {
            'state': task.state,
            'status': 'Okänd status'
        }
    
    return render_template('main/transcription_status.html', response=response, task_id=task_id)

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
                # Spara original-ljudet tillfälligt
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.' + file.filename.split('.')[-1])
                file.save(temp_file.name)
                temp_file.close()
                
                current_app.logger.info(f"Sparade fil tillfälligt till: {temp_file.name}")
                
                # Hämta titel från formuläret
                title = request.form.get('title')
                if not title or title.strip() == '':
                    title = 'Transkription ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
                
                # Starta Celery task
                from app.tasks.transcription_tasks import process_transcription
                task = process_transcription.delay(temp_file.name, title, current_user.id)
                
                current_app.logger.info(f"Startade Celery-task med ID: {task.id}")
                
                # Redirect to status page
                flash('Din transkription bearbetas. Du kommer att meddelas när den är klar.', 'info')
                return redirect(url_for('main.transcription_status', task_id=task.id))
                
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

@main.route('/api/task_status/<task_id>', methods=['GET'])
@login_required
def api_task_status(task_id):
    """API endpoint for checking task status."""
    from app.celery_worker import celery
    
    task = celery.AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Pending'
        }
    elif task.state == 'PROCESSING_AUDIO':
        response = {
            'state': task.state,
            'status': 'Processing audio'
        }
    elif task.state == 'TRANSCRIBING':
        response = {
            'state': task.state,
            'status': 'Transcribing audio'
        }
    elif task.state == 'GENERATING_SUMMARY':
        response = {
            'state': task.state,
            'status': 'Generating summary'
        }
    elif task.state == 'SAVING':
        response = {
            'state': task.state,
            'status': 'Saving transcription'
        }
    elif task.state == 'FAILURE':
        # Something went wrong in the background job
        response = {
            'state': task.state,
            'status': 'Failed',
            'error': str(task.info)
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'status': 'Completed'
        }
        # Add transcription ID if available
        if isinstance(task.info, dict) and 'transcription_id' in task.info:
            response['transcription_id'] = task.info['transcription_id']
            response['title'] = task.info.get('title', 'Transcription')
    else:
        # Something unexpected
        response = {
            'state': task.state,
            'status': 'Unknown status'
        }
    
    return jsonify(response)

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


@main.route('/progress-status')
@login_required
def progress_status():
    """API endpoint för att hämta framstegsstatus för aktiva uppgifter."""
    # Hämta det senaste task_id:t från session om det finns
    task_id = session.get('current_task_id')
    
    if not task_id:
        return jsonify({"message": "Ingen aktiv process hittades"}), 404
    
    # Hämta status om task_id finns
    from app.utils.progress_tracker import get_task_status
    status = get_task_status(task_id)
    
    if status:
        return jsonify({
            "task_id": task_id,
            "status": status
        })
    
    # Hämta status från Celery om den inte finns i progress_tracker
    from app.celery_worker import celery
    task = celery.AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {
            "task_id": task_id,
            "status": {
                "progress": 0,
                "status": "pending",
                "message": "Uppgiften väntar på att bearbetas..."
            }
        }
    elif task.state == 'FAILURE':
        response = {
            "task_id": task_id,
            "status": {
                "progress": 0,
                "status": "error",
                "message": f"Ett fel uppstod: {str(task.info)}"
            }
        }
    else:
        response = {
            "task_id": task_id,
            "status": {
                "progress": 50,  # Uppskattning
                "status": "processing",
                "message": f"Status: {task.state}"
            }
        }
    
    return jsonify(response)


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
        
        # Save original audio temporarily
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.' + audio_file.filename.split('.')[-1])
        audio_file.save(temp_file.name)
        temp_file.close()
        
        current_app.logger.info(f"Saved file temporarily to: {temp_file.name}")
        
        # Get title from form
        title = request.form.get('title', 'API Transcription')
        
        # Start Celery task
        from app.tasks.transcription_tasks import process_transcription
        task = process_transcription.delay(temp_file.name, title, current_user.id)
        
        # Return task ID for status checking
        return jsonify({
            "status": "processing",
            "task_id": task.id,
            "message": "Transcription is being processed"
        })
        
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except RuntimeError as re:
        return jsonify({"error": str(re)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500