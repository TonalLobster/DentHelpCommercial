"""
Routes för att hantera Server-Sent Events (SSE) för realtidsuppdateringar 
av transkriptionsprocessen.
"""
import json
import time
from flask import Blueprint, Response, request, stream_with_context
from flask_login import login_required, current_user
from app.utils.progress_tracker import get_task_status, clean_old_tasks

# Create the SSE blueprint
sse = Blueprint('sse', __name__)

@sse.route('/progress/<task_id>')
@login_required
def progress_stream(task_id):
    """
    SSE-endpoint för att skicka realtidsuppdateringar om transkriptionsprocessen.
    Använder Server-Sent Events (SSE) för att strömma status till klienten.
    """
    def generate():
        # Skicka en initial anslutningshändelse
        yield f"data: {json.dumps({'event': 'connected', 'task_id': task_id})}\n\n"
        
        # Hjälpvariabler för att begränsa uppdateringsfrekvensen
        count = 0
        last_status = None
        
        # Strömma uppdateringar
        while True:
            count += 1
            status = get_task_status(task_id)
            
            if status is None:
                # Uppgiften finns inte, avsluta strömmen
                yield f"data: {json.dumps({'event': 'error', 'message': 'Uppgiften finns inte eller har utgått'})}\n\n"
                break
            
            # Skapa en händelse om statusen har ändrats
            send_update = (
                last_status is None or 
                status != last_status or 
                count % 3 == 0  # Skicka även uppdateringar med jämna mellanrum
            )
            
            if send_update:
                # Skapa en uppdateringshändelse
                update_event = {
                    'event': 'update' if status['status'] != 'completed' else 'completed',
                    'data': status,
                    'task_id': task_id
                }
                
                yield f"data: {json.dumps(update_event)}\n\n"
                last_status = status.copy()
            
            # Om bearbetningen är klar eller ett fel uppstått, avsluta strömmen
            if status['status'] in ('completed', 'error'):
                yield f"data: {json.dumps({'event': 'completed', 'data': status, 'task_id': task_id})}\n\n"
                break
                
            # Pausa en kort stund mellan uppdateringar
            time.sleep(1)
            
            # Rensa gamla uppgifter för att förhindra minnesläckage
            if count % 60 == 0:  # Var 60:e sekund
                clean_old_tasks()
    
    # Skapa en strömmande respons med MIME-typen text/event-stream
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'  # Viktigt för vissa proxy-servrar (Nginx)
        }
    )