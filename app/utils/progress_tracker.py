"""
Progress tracking utility för DentalScribe AI.
Spårar och rapporterar framsteg för transkriptionsprocessen i realtid.
"""

import time
import json
import uuid
import threading

# Dictionary för att lagra framstegsdata för varje transkriptionsprocess
_progress_store = {}

def generate_task_id():
    """Generera ett unikt ID för en bearbetningsuppgift."""
    return str(uuid.uuid4())

def register_task(task_id=None):
    """
    Registrera en ny bearbetningsuppgift och returnera dess ID.
    
    Funktionen initierar ett statusobjekt med angivna steg:
    - compression: Komprimeringsfasen.
    - transcription: Transkriberingsfasen.
    - summary: Sammanfattningsfasen.
    - saving: Sparningsfasen.
    """
    task_id = task_id or generate_task_id()
    _progress_store[task_id] = {
        'progress': 0,
        'status': 'initializing',
        'message': 'Förbereder bearbetning...',
        'time_left': None,
        'steps': {
            'compression': 'waiting',
            'transcription': 'waiting',
            'summary': 'waiting',
            'saving': 'waiting'
        },
        'start_time': time.time(),
        'last_update': time.time(),
        'size_info': {
            'original': None,
            'compressed': None
        },
        'errors': []
    }
    return task_id

def update_task_status(task_id, progress=None, status=None, message=None, 
                       time_left=None, step=None, step_status=None, 
                       size_info=None, error=None):
    """
    Uppdatera status för en bearbetningsuppgift.
    
    Parametrar:
      - progress: Nuvarande progress i procent.
      - status: Övergripande status (t.ex. 'initializing', 'completed', 'error').
      - message: Statusmeddelande att visa.
      - time_left: Uppskattad tid kvar (i sekunder).
      - step: Namn på steget att uppdatera (exempelvis 'compression', 'transcription', etc.).
      - step_status: Status för det specifika steget ('waiting', 'active', 'completed' eller 'error').
      - size_info: Ordbok med filstorleksinformation, t.ex. {'original': bytes, 'compressed': bytes}.
      - error: Om ett fel inträffat, läggs det in här.
    """
    if task_id not in _progress_store:
        return False

    task = _progress_store[task_id]
    
    if progress is not None:
        task['progress'] = progress

    if status is not None:
        task['status'] = status

    if message is not None:
        task['message'] = message

    if time_left is not None:
        task['time_left'] = time_left
        
    if step is not None and step_status is not None:
        task['steps'][step] = step_status

    if size_info is not None:
        for key, value in size_info.items():
            task['size_info'][key] = value

    if error is not None:
        task['errors'].append({
            'time': time.time(),
            'message': str(error)
        })
        # Om ett fel rapporteras, sätt status till 'error' om det inte redan satts
        if status is None:
            task['status'] = 'error'

    task['last_update'] = time.time()
    return True

def get_task_status(task_id):
    """Hämta status för en bearbetningsuppgift med givet ID."""
    return _progress_store.get(task_id)

def remove_task(task_id):
    """Ta bort en slutförd bearbetningsuppgift."""
    if task_id in _progress_store:
        del _progress_store[task_id]
        return True
    return False

def clean_old_tasks(max_age=3600):
    """
    Rensa bort gamla uppgifter som inte uppdaterats under max_age sekunder
    (standard är 1 timme) för att förhindra minnesläckage.
    """
    now = time.time()
    for task_id in list(_progress_store.keys()):
        task = _progress_store[task_id]
        if now - task['last_update'] > max_age:
            remove_task(task_id)

def format_size(size_bytes):
    """Formatera filstorlek från bytes till ett läsbart format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.1f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.1f} GB"

def start_cleanup_thread():
    """
    Starta en bakgrundstråd som regelbundet rensar bort gamla uppgifter.
    
    Rensningen körs var 10:e minut som standard.
    """
    def cleanup_loop():
        while True:
            clean_old_tasks()
            time.sleep(600)  # 600 sekunder = 10 minuter

    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    return thread
