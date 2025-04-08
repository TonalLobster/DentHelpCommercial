"""
Forms for DentalScribe application.
Centralizes form definitions to improve code organization.
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, SubmitField
from wtforms.validators import Optional, Length

class TranscriptionForm(FlaskForm):
    """
    Form for creating a new transcription with audio file upload.
    Provides validation for title and audio file.
    """
    title = StringField(
        'Titel', 
        validators=[
            Optional(), 
            Length(min=0, max=100, message='Titel får vara max 100 tecken')
        ],
        render_kw={'placeholder': 'Valfri titel för transkriptionen'}
    )
    
    audio = FileField(
        'Ljudfil', 
        validators=[
            FileRequired(message='Vänligen välj en ljudfil'),
            FileAllowed(
                ['wav', 'mp3', 'm4a', 'ogg'], 
                message='Endast WAV, MP3, M4A och OGG-filer är tillåtna!'
            )
        ]
    )
    
    submit = SubmitField('Transkribera')