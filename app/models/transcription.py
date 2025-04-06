"""
Transcription model for storing audio transcription data.
"""
from datetime import datetime
from app import db

class Transcription(db.Model):
    """Model for dental appointment transcriptions."""
    
    __tablename__ = 'transcriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, default='Untitled Transcription')
    transcription_text = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=True)  # Stored as JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    patient_id = db.Column(db.String(50), nullable=True)
    
    # Optional: Add additional metadata columns
    audio_duration = db.Column(db.Integer, nullable=True)  # Duration in seconds
    patient_ref = db.Column(db.String(50), nullable=True)  # Optional patient reference
    notes = db.Column(db.Text, nullable=True)  # Additional notes
    
    def __repr__(self):
        return f'<Transcription {self.title}>'
    
    def to_dict(self):
        """Convert transcription to dictionary for API responses."""
        return {
            'id': self.id,
            'title': self.title,
            'transcription_text': self.transcription_text,
            'summary': self.summary,  # Client should parse this JSON
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'user_id': self.user_id,
            'audio_duration': self.audio_duration,
            'patient_ref': self.patient_ref,
            'notes': self.notes
        }