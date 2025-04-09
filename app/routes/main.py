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
    """Page for creating new transcriptions."""
    # Create a simple form for CSRF protection
    form = FlaskForm()
    
    if request.method == 'POST':
        # Debugging och loggning
        current_app.logger.info("POST request received for transcription")
        current_app.logger.info(f"Files in request: {list(request.files.keys())}")
        current_app.logger.info(f"Form data: {list(request.form.keys())}")
        current_app.logger.info(f"Content type: {request.headers.get('Content-Type', 'Not provided')}")
        
        # Skapa en ny uppgift för framstegsspårning
        task_id = register_task()
        
        # Spara uppgifts-ID i sessionen så klienten kan hämta framsteg
        session['transcription_task_id'] = task_id
        
        # Kontrollera att fil skickades med
        if 'audio' not in request.files:
            current_app.logger.warning("No file in request")
            update_task_status(
                task_id,
                status='error',
                message='Ingen fil i förfrågan',
                error='No file in request'
            )
            return jsonify({'error': 'Ingen fil hittades i förfrågan', 'task_id': task_id}), 400
        
        file = request.files['audio']
        current_app.logger.info(f"Fil mottagen: {file.filename}")
        
        # Om ingen fil valts
        if file.filename == '':
            current_app.logger.warning("Filnamn är tomt")
            update_task_status(
                task_id,
                status='error',
                message='Ingen fil vald',
                error='Empty filename'
            )
            return jsonify({'error': 'Ingen fil vald', 'task_id': task_id}), 400
        
        if file and allowed_file(file.filename):
            try:
                # ---------------------------
                # Steg 1: Komprimering
                # ---------------------------
                # Starta komprimeringssteget
                update_task_status(
                    task_id,
                    progress=0,
                    message='Startar komprimering...',
                    step='compression',
                    step_status='active'
                )
                processed_audio, processing_error = process_audio(file, task_id)
                # Uppdatera status när komprimeringen är klar
                update_task_status(
                    task_id,
                    progress=20,
                    message='Komprimering klar',
                    step='compression',
                    step_status='completed'
                )
                
                # ---------------------------
                # Steg 2: Transkribering
                # ---------------------------
                update_task_status(
                    task_id,
                    progress=20,
                    message='Startar transkribering...',
                    step='transcription',
                    step_status='active'
                )
                transcription_text = transcribe_audio(processed_audio, task_id)
                update_task_status(
                    task_id,
                    progress=40,
                    message='Transkribering klar',
                    step='transcription',
                    step_status='completed'
                )
                
                # ---------------------------
                # Steg 3: Sammanfattning
                # ---------------------------
                update_task_status(
                    task_id,
                    progress=40,
                    message='Genererar sammanfattning...',
                    step='summary',
                    step_status='active'
                )
                summary_dict = generate_summary(transcription_text, task_id)
                update_task_status(
                    task_id,
                    progress=60,
                    message='Sammanfattning klar',
                    step='summary',
                    step_status='completed'
                )
                
                # ---------------------------
                # Steg 4: Spara Resultat
                # ---------------------------
                # Förbered en temporär progressuppdatering innan sparande
                update_task_status(
                    task_id,
                    progress=60,
                    message=f'Sparar transkription...',
                    step='saving',
                    step_status='active'
                )
                
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
                
                # Uppdatera status vid sparande till databas
                update_task_status(
                    task_id,
                    progress=95,
                    message='Sparar till databas...',
                    step='saving',
                    step_status='active',
                    time_left=1
                )
                db.session.add(new_transcription)
                db.session.commit()
                current_app.logger.info(f"Transkription sparad med ID: {new_transcription.id}")
                
                update_task_status(
                    task_id,
                    progress=100,
                    status='completed',
                    message='Transkription slutförd och sparad!',
                    step='saving',
                    step_status='completed',
                    time_left=0
                )
                
                # Returnera svar med redirect och task_id
                return jsonify({
                    'redirect': url_for('main.view_transcription', id=new_transcription.id),
                    'task_id': task_id
                })
                
            except ValueError as ve:
                current_app.logger.error(f"Valideringsfel: {str(ve)}")
                update_task_status(
                    task_id,
                    status='error',
                    message=f'Valideringsfel: {str(ve)}',
                    error=str(ve)
                )
                return jsonify({'error': f'Valideringsfel: {str(ve)}', 'task_id': task_id}), 400
                
            except RuntimeError as re:
                current_app.logger.error(f"Körningsfel: {str(re)}")
                update_task_status(
                    task_id,
                    status='error',
                    message=f'Körningsfel: {str(re)}',
                    error=str(re)
                )
                return jsonify({'error': f'Körningsfel: {str(re)}', 'task_id': task_id}), 500
                
            except Exception as e:
                current_app.logger.error(f"Oväntat fel vid transkribering: {str(e)}", exc_info=True)
                update_task_status(
                    task_id,
                    status='error',
                    message=f'Ett oväntat fel inträffade: {str(e)}',
                    error=str(e)
                )
                return jsonify({'error': f'Ett oväntat fel inträffade: {str(e)}', 'task_id': task_id}), 500
        else:
            current_app.logger.warning(f"Otillåten filtyp: {file.filename}")
            update_task_status(
                task_id,
                status='error',
                message=f'Otillåten filtyp: {file.filename}',
                error=f'Otillåten filtyp: {file.filename}'
            )
            return jsonify({'error': 'Filtypen är inte tillåten. Vänligen ladda upp WAV, MP3, M4A eller OGG.', 'task_id': task_id}), 400
    
    return render_template('main/transcribe.html', form=form)

@main.route('/progress-status')
@login_required
def get_progress_status():
    """API endpoint för att hämta nuvarande status för bearbetningsuppgift."""
    task_id = session.get('transcription_task_id')
    
    if not task_id:
        return jsonify({"error": "Ingen aktiv transkriptionsuppgift hittades"}), 404
    
    status = get_task_status(task_id)
    
    if not status:
        return jsonify({"error": "Uppgiften hittades inte"}), 404
        
    return jsonify({"task_id": task_id, "status": status})

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
        task_id = register_task()
        
        if 'audio' not in request.files:
            update_task_status(
                task_id,
                status='error',
                message='Ingen ljudfil skickades',
                error='No audio file sent'
            )
            return jsonify({"error": "No audio file sent", "task_id": task_id}), 400
        
        audio_file = request.files['audio']
        if not audio_file.filename:
            update_task_status(
                task_id,
                status='error',
                message='Fil utan namn skickades',
                error='File without name sent'
            )
            return jsonify({"error": "File without name sent", "task_id": task_id}), 400
        
        if request.content_length and request.content_length > 100 * 1024 * 1024:
            update_task_status(
                task_id,
                status='error',
                message='Filen är för stor. Maximal filstorlek är 100MB.',
                error='File is too large'
            )
            return jsonify({"error": "File is too large. Maximum file size is 100MB.", "task_id": task_id}), 413
        
        temp_original = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        audio_file.save(temp_original.name)
        audio_file.seek(0)
        
        try:
            update_task_status(
                task_id,
                progress=0,
                message='Startar komprimering...',
                step='compression',
                step_status='active'
            )
            processed_audio, processing_error = process_audio(audio_file, task_id)
            update_task_status(
                task_id,
                progress=20,
                message='Komprimering klar',
                step='compression',
                step_status='completed'
            )
        except Exception as e:
            current_app.logger.error(f"Fel vid ljudbearbetning: {str(e)}")
            update_task_status(
                task_id,
                status='error',
                message=f'Fel vid ljudbearbetning: {str(e)}',
                error=str(e)
            )
            with open(temp_original.name, 'rb') as f:
                processed_audio = f
                audio_file = f
        
        try:
            update_task_status(
                task_id,
                progress=20,
                message='Startar transkribering...',
                step='transcription',
                step_status='active'
            )
            transcription_text = transcribe_audio(processed_audio, task_id)
            update_task_status(
                task_id,
                progress=40,
                message='Transkribering klar',
                step='transcription',
                step_status='completed'
            )
        except Exception as e:
            current_app.logger.error(f"Fel vid transkribering: {str(e)}")
            update_task_status(
                task_id,
                status='error',
                message=f'Fel vid transkribering: {str(e)}',
                error=str(e)
            )
            with open(temp_original.name, 'rb') as f:
                transcription_text = transcribe_audio(f, task_id)
        
        update_task_status(
            task_id,
            progress=40,
            message='Genererar sammanfattning...',
            step='summary',
            step_status='active'
        )
        summary_dict = generate_summary(transcription_text, task_id)
        update_task_status(
            task_id,
            progress=60,
            message='Sammanfattning klar',
            step='summary',
            step_status='completed'
        )
        
        if request.form.get('save', 'true').lower() == 'true':
            update_task_status(
                task_id,
                progress=60,
                message='Sparar transkription...',
                step='saving',
                step_status='active'
            )
            new_transcription = Transcription(
                title=request.form.get('title', 'API Transcription'),
                user_id=current_user.id,
                transcription_text=transcription_text,
                summary=json.dumps(summary_dict, ensure_ascii=False)
            )
            db.session.add(new_transcription)
            db.session.commit()
            update_task_status(
                task_id,
                progress=100,
                status='completed',
                message='Transkription sparad!',
                step='saving',
                step_status='completed',
                time_left=0
            )
            summary_dict['transcription_id'] = new_transcription.id
        else:
            update_task_status(
                task_id,
                progress=100,
                status='completed',
                message='Transkription slutförd (ej sparad)!',
                step='saving',
                step_status='completed',
                time_left=0
            )
        
        if os.path.exists(temp_original.name):
            os.unlink(temp_original.name)
        
        response_data = {
            'summary': summary_dict,
            'transcription': transcription_text,
            'task_id': task_id
        }
        
        return jsonify(response_data)
    
    except ValueError as ve:
        if 'task_id' in locals():
            update_task_status(
                task_id,
                status='error',
                message=f'Valideringsfel: {str(ve)}',
                error=str(ve)
            )
        return jsonify({"error": str(ve), "task_id": task_id if 'task_id' in locals() else None}), 400
    except RuntimeError as re:
        if 'task_id' in locals():
            update_task_status(
                task_id,
                status='error',
                message=f'Körningsfel: {str(re)}',
                error=str(re)
            )
        return jsonify({"error": str(re), "task_id": task_id if 'task_id' in locals() else None}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        if 'task_id' in locals():
            update_task_status(
                task_id,
                status='error',
                message=f'Ett oväntat fel inträffade: {str(e)}',
                error=str(e)
            )
        return jsonify({"error": f"An unexpected error occurred: {str(e)}", "task_id": task_id if 'task_id' in locals() else None}), 500
