from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
import os
import tempfile
from werkzeug.utils import secure_filename
from app import db
from app.models.transcription import Transcription
from app.services.transcription_service import transcribe_audio_file
from app.services.summary_service import generate_summary

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Get user's transcriptions
    transcriptions = Transcription.query.filter_by(user_id=current_user.id).order_by(Transcription.created_at.desc()).all()
    return render_template('main/dashboard.html', transcriptions=transcriptions)

@main_bp.route('/transcribe', methods=['GET', 'POST'])
@login_required
def transcribe():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'audio_file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['audio_file']
        
        # If user does not select file, browser also
        # submits an empty part without filename
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if file:
            try:
                # Reset file pointer
                file.seek(0)
                
                # Transcribe audio
                transcription_text = transcribe_audio_file(file)
                
                # Generate summary
                patient_id = request.form.get('patient_id', '')
                summary = generate_summary(transcription_text)
                
                # Save to database
                filename = secure_filename(file.filename)
                transcription = Transcription(
                    user_id=current_user.id,
                    patient_id=patient_id,
                    text=transcription_text,
                    audio_filename=filename
                )
                transcription.summary = summary
                
                db.session.add(transcription)
                db.session.commit()
                
                flash('Transcription completed successfully', 'success')
                return redirect(url_for('main.view_transcription', id=transcription.id))
                
            except Exception as e:
                current_app.logger.error(f"Error during transcription: {str(e)}")
                flash(f'Error during transcription: {str(e)}', 'error')
                return redirect(request.url)
    
    return render_template('main/transcribe.html')

@main_bp.route('/transcription/<int:id>')
@login_required
def view_transcription(id):
    transcription = Transcription.query.get_or_404(id)
    
    # Ensure the user can only view their own transcriptions
    if transcription.user_id != current_user.id:
        flash('You do not have permission to view this transcription', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('main/view_transcription.html', transcription=transcription)