"""
Seed script to initialize the database with sample data.
Run with 'flask --app seed.py seed-db'
"""

import click
from flask import Flask
from flask.cli import with_appcontext
from app import db, create_app
from app.models.user import User
from app.models.transcription import Transcription
import datetime

app = create_app()

@app.cli.command('seed-db')
@with_appcontext
def seed_db():
    """Seed the database with sample data."""
    # Create users
    click.echo('Creating sample users...')
    
    # Admin user
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@dentalscribe.ai',
            license_number='ADMIN001'
        )
        admin.set_password('admin123')
        db.session.add(admin)
    
    # Sample dentist
    dentist = User.query.filter_by(username='dentist').first()
    if not dentist:
        dentist = User(
            username='dentist',
            email='dentist@example.com',
            license_number='SWE12345'
        )
        dentist.set_password('dentist123')
        db.session.add(dentist)
    
    db.session.commit()
    
    # Create sample transcriptions
    click.echo('Creating sample transcriptions...')
    
    # Only add sample transcriptions if they don't exist
    if Transcription.query.count() == 0:
        sample_transcription1 = Transcription(
            user_id=dentist.id,
            patient_id='P12345',
            text="""Hej och välkommen till din undersökning idag. Hur mår du?
Jag har haft lite ont i en tand på höger sida när jag äter söta saker.
Okej, låt mig ta en titt. Öppna stort. Jag ser en liten karies i tand 16, och det kan vara orsaken till smärtan. Vi behöver åtgärda detta med en liten fyllning. Har du några andra problem eller frågor?
Nej, det är bara den tanden som stör mig.
Perfekt, då gör vi en tid för att laga den. Du behöver också förbättra din munhygien lite, särskilt runt bakre tänderna. Jag rekommenderar att använda mellanrumsborstar dagligen.""",
            created_at=datetime.datetime.now() - datetime.timedelta(days=10)
        )
        
        sample_transcription1.summary = {
            "Patient Complaints": ["Smärta i tand på höger sida vid konsumtion av sötsaker"],
            "Clinical Findings": ["Karies i tand 16", "Bristfällig munhygien runt bakre tänderna"],
            "Diagnosis": ["Karies i tand 16"],
            "Treatment Plan": ["Fyllning i tand 16"],
            "Follow-up Recommendations": ["Förbättra munhygien", "Använda mellanrumsborstar dagligen"]
        }
        
        sample_transcription2 = Transcription(
            user_id=dentist.id,
            patient_id='P67890',
            text="""God morgon! Hur är det med dig idag?
Jo tack, men mina tänder är väldigt känsliga för kall mat och dryck.
Jag förstår. Låt mig undersöka dina tänder. Ah, jag ser att du har lite tandhalserosion, särskilt på tänderna 13 till 23. Detta är vanligtvis orsaken till känslighet som du beskriver. Använder du någon speciell tandkräm?
Bara vanlig tandkräm, inget särskilt.
Jag rekommenderar att du börjar använda en tandkräm speciellt för känsliga tänder, som innehåller kaliumnitrat eller liknande ämnen. Det hjälper till att blockera smärtsignalerna. Jag ser också att ditt tandkött är lite inflammerat. Borstar du två gånger om dagen?
Ja, men jag är inte så bra på att använda tandtråd.
Daglig tandtråd eller mellanrumsborstar är viktigt. Vi behöver också göra en professionell tandrengöring för att ta bort tandsten, det kommer hjälpa med tandköttsinflammationen. Ska vi boka in det?""",
            created_at=datetime.datetime.now() - datetime.timedelta(days=3)
        )
        
        sample_transcription2.summary = {
            "Patient Complaints": ["Känslighet i tänderna för kall mat och dryck"],
            "Clinical Findings": ["Tandhalserosion på tänderna 13-23", "Inflammerat tandkött", "Tandsten"],
            "Diagnosis": ["Dentinkänslighet", "Gingivit"],
            "Treatment Plan": ["Professionell tandrengöring"],
            "Follow-up Recommendations": ["Använda tandkräm för känsliga tänder med kaliumnitrat", "Börja använda tandtråd eller mellanrumsborstar dagligen"]
        }
        
        db.session.add(sample_transcription1)
        db.session.add(sample_transcription2)
        db.session.commit()
    
    click.echo('Database seeded successfully!')

if __name__ == '__main__':
    with app.app_context():
        seed_db()