from app import db
from datetime import datetime
import json

class Transcription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient_id = db.Column(db.String(64), nullable=True)
    text = db.Column(db.Text, nullable=False)
    summary_json = db.Column(db.Text, nullable=True)
    audio_filename = db.Column(db.String(255), nullable=True)
    
    @property
    def summary(self):
        if self.summary_json:
            return json.loads(self.summary_json)
        return None
        
    @summary.setter
    def summary(self, summary_dict):
        self.summary_json = json.dumps(summary_dict)
    
    def __repr__(self):
        return f'<Transcription {self.id}>'