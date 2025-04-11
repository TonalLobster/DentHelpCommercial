"""
Routes for Celery task management and monitoring.
"""
from flask import Blueprint, jsonify, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from celery.result import AsyncResult

celery_bp = Blueprint('celery', __name__)

@celery_bp.route('/status/<task_id>')
@login_required
def task_status_page(task_id):
    """Show status page for a specific task."""
    return render_template('celery/task_status.html', task_id=task_id)

@celery_bp.route('/api/status/<task_id>')
@login_required
def task_status(task_id):
    """API endpoint to check task status."""
    task = AsyncResult(task_id)
    
    if task.state == 'PENDING':
        # Task is pending
        response = {
            'state': task.state,
            'status': 'Task is pending...',
            'progress': 0
        }
    elif task.state == 'FAILURE':
        # Task failed
        error_msg = 'Unknown error'
        if hasattr(task, 'info') and task.info:
            if isinstance(task.info, Exception):
                error_msg = str(task.info)
            elif isinstance(task.info, dict) and 'error' in task.info:
                error_msg = task.info['error']
                
        response = {
            'state': task.state,
            'status': 'Transkriptionen misslyckades',
            'error': error_msg,
            'progress': 0
        }
    elif task.state in ['INITIALIZING', 'PROCESSING', 'TRANSCRIBING', 'SUMMARIZING', 'SAVING']:
        # Custom states
        progress_map = {
            'INITIALIZING': 10,
            'PROCESSING': 25,
            'TRANSCRIBING': 50,
            'SUMMARIZING': 75,
            'SAVING': 90
        }
        
        status_message = task.info.get('status', f'State: {task.state}') if hasattr(task, 'info') and task.info else f'State: {task.state}'
        
        response = {
            'state': task.state,
            'status': status_message,
            'progress': progress_map.get(task.state, 0)
        }
    elif task.state == 'SUCCESS':
        # Task completed successfully
        if task.info and isinstance(task.info, dict) and 'transcription_id' in task.info:
            # Return transcription data
            response = {
                'state': task.state,
                'status': 'Transkription slutförd!',
                'progress': 100,
                'result': task.info,
                'transcription_id': task.info.get('transcription_id'),
                'redirect_url': url_for('main.view_transcription', id=task.info.get('transcription_id'))
            }
        else:
            response = {
                'state': task.state,
                'status': 'Task completed, but no transcription data found',
                'progress': 100,
                'result': str(task.info)
            }
    else:
        # Unknown state
        response = {
            'state': task.state,
            'status': f'Unknown state: {task.state}',
            'progress': 0
        }
    
    return jsonify(response)

@celery_bp.route('/cancel/<task_id>', methods=['POST'])
@login_required
def cancel_task(task_id):
    """Cancel a running task."""
    task = AsyncResult(task_id)
    
    if task.state in ['PENDING', 'INITIALIZING', 'PROCESSING', 'TRANSCRIBING', 'SUMMARIZING', 'SAVING']:
        task.revoke(terminate=True)
        flash('Transkriptionen har avbrutits', 'info')
    else:
        flash(f'Kan inte avbryta uppgift i tillstånd: {task.state}', 'warning')
        
    return redirect(url_for('main.dashboard'))