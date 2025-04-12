# DentalScribe AI: Heroku Migration Guide

Här är en omfattande guide för att migrera din DentalScribe AI-app till Heroku och implementera de förbättringar vi diskuterat. Denna guide fokuserar på att skapa en solid MVP samtidigt som vi förbereder för framtida utbyggnad.

## 1. Projektstruktur för Heroku

Skapa följande struktur för ditt nya repo:

```
dental-scribe-ai/
│
├── app/
│   ├── __init__.py             # Flask-app initiering
│   ├── routes/                 # API-endpoints
│   ├── models/                 # Databasmodeller
│   ├── services/               # Affärslogik (transkribering, etc.)
│   ├── static/                 # CSS, JS, bilder
│   └── templates/              # HTML-templates
│
├── migrations/                 # Databasmigrationer (Flask-Migrate)
├── .env.example                # Mall för miljövariabler
├── .gitignore                  # Git-ignorerade filer
├── Procfile                    # Heroku processdefinition
├── requirements.txt            # Paketberoenden
├── runtime.txt                 # Python-version
└── wsgi.py                     # Entrypoint för webserver
```

## 2. Teknologival

### Backend
- **Flask**: Lättare och mer flexibelt än Django för din användning
- **SQLAlchemy**: ORM för databasinteraktion
- **Flask-Migrate**: För att hantera databasschemaändringar
- **Gunicorn**: Produktionsredo WSGI-server
- **Flask-Login**: För autentiseringshantering

### Frontend
- **Tailwind CSS**: Passar bättre för Heroku eftersom det har mindre overhead än Material UI och kräver inte React som beroende
- **Alpine.js**: Lättvikts JavaScript-ramverk för interaktivitet utan att behöva React
- **HTML Templates**: Använd Jinja2 (Flask's standardtemplating)

### Databas
- **Heroku Postgres**: Enkel integration med Heroku

## 3. Steg-för-steg implementationsplan

### A. Konfigurera Heroku-miljön
1. Skapa ett Heroku-konto om du inte redan har ett
2. Installera Heroku CLI
3. Skapa en ny Heroku-app: `heroku create dental-scribe-ai`
4. Lägg till PostgreSQL: `heroku addons:create heroku-postgresql:mini`
5. Konfigurera miljövariabler: `heroku config:set OPENAI_API_KEY=your_key`

### B. Konfigurera grundläggande Flask-app
1. Skapa Flask-app med blueprint-struktur
2. Konfigurera SQLAlchemy för databashantering
3. Skapa modeller för användare och transkriptioner
4. Implementera grundläggande autentisering med Flask-Login
5. Konfigurera migrations-support med Flask-Migrate

### C. Migrera nuvarande funktionalitet
1. Implementera ljuduppladdning och inspelning
2. Integrera OpenAI API för transkribering
3. Implementera sammanfattningsgenerering
4. Skapa användargränssnitt med Tailwind CSS
5. Migrera användarhantering från SQLite till PostgreSQL

### D. Heroku-specifika anpassningar
1. Skapa Procfile: `web: gunicorn wsgi:app`
2. Konfigurera `runtime.txt` med Python 3.9+
3. Anpassa databasanslutningssträngar för att hantera Heroku-miljö
4. Konfigurera statiska filer för att fungera med Heroku

### E. Säkerhet och tillförlitlighet
1. Implementera CSRF-skydd
2. Konfigurera säker hantering av användarautentisering
3. Säkerställ att känslig data (API-nycklar) hanteras korrekt
4. Implementera loggning för felsökning
5. Lägg till rate-limiting för att förhindra API-missbruk

## 4. Viktigaste kodändringar

### Databasmigrering från SQLite till PostgreSQL

```python
# config.py
import os

class Config:
    # Hämta databas-URL från Heroku om tillgänglig, annars använd lokal
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://localhost/dental_scribe')
    
    # Fixa Heroku PostgreSQL-URL (de använder 'postgres://' istället för 'postgresql://')
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
```

### Användare och autentiseringsmodell

```python
# app/models/user.py
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    license_number = db.Column(db.String(64), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
```

### Transkriptions- och sammanfattningsmodell

```python
# app/models/transcription.py
from app import db
from datetime import datetime
import json

class Transcription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    text = db.Column(db.Text, nullable=False)
    summary_json = db.Column(db.Text, nullable=True)
    
    @property
    def summary(self):
        if self.summary_json:
            return json.loads(self.summary_json)
        return None
        
    @summary.setter
    def summary(self, summary_dict):
        self.summary_json = json.dumps(summary_dict)
```

### OpenAI API-integration

```python
# app/services/transcription_service.py
import openai
from flask import current_app
import tempfile
import os

def transcribe_audio_file(audio_file):
    """Transcribe audio using OpenAI Whisper API"""
    try:
        openai.api_key = current_app.config['OPENAI_API_KEY']
        
        # Spara den uppladdade filen tillfälligt
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
            tmp.write(audio_file.read())
            tmp_name = tmp.name
        
        with open(tmp_name, 'rb') as audio:
            transcription = openai.Audio.transcribe(
                model="whisper-1",
                file=audio,
                language="sv"
            )
        
        # Ta bort temp-filen
        os.unlink(tmp_name)
        return transcription.text
        
    except Exception as e:
        current_app.logger.error(f"Transcription error: {str(e)}")
        raise
```

### Procfile för Heroku

```
web: gunicorn wsgi:app
```
### requirements.txt för Heroku

```
Flask==3.1.0
Flask-SQLAlchemy==3.1.0
Flask-Migrate==4.0.5
Flask-Login==0.6.3
gunicorn==23.0.0
psycopg2-binary==2.9.9
python-dotenv==1.0.1
openai==1.66.3
Werkzeug==3.0.2
```

## 5. Viktiga Heroku-anpassningar

1. **Dynamiska portar**: Heroku tilldelar en dynamisk port som du måste lyssna på:
```python
# wsgi.py
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
```

2. **Hantera miljövariabler** för dev/prod:
```python
# .env.example
FLASK_APP=wsgi.py
FLASK_ENV=development
OPENAI_API_KEY=your_openai_api_key_here
SECRET_KEY=your_secret_key_here
```

3. **Release fas** i Procfile för att köra databasmigrationer:
```
release: flask db upgrade
web: gunicorn wsgi:app
```

## 6. Deployment-process

1. Initialisera Git-repo:
```bash
git init
git add .
git commit -m "Initial commit"
```

2. Konfigurera Heroku-remote:
```bash
heroku git:remote -a dental-scribe-ai
```

3. Pusha koden till Heroku:
```bash
git push heroku main
```

4. Konfigurera databasmigrationer:
```bash
heroku run flask db upgrade
```

5. Sätt upp initiala data (t.ex. giltiga tandläkar-ID):
```bash
heroku run flask seed-db
```

## 7. Nästa steg efter MVP

1. **Analytics & Monitoring**:
   - Integrera Heroku Metrics för grundläggande övervakning
   - Lägg till New Relic för avancerad övervakning

2. **Skalning**:
   - Konfigurera autoskalning av dynos baserat på belastning
   - Optimera databasanvändningen

3. **CI/CD Pipeline**:
   - Konfigurera GitHub Actions för test och automatisk deployment

4. **Kostnadskontroll**:
   - Övervaka användning av Heroku-resurser
   - Optimera för att hålla kostnaderna nere medan appen skalas

Denna guide ger dig en solid grund för att migrera din DentalScribe AI-app till Heroku. När vi fortsätter arbeta i detta projekt, kommer vi kunna ta itu med specifika utmaningar mer detaljerat och bygga ut appen steg för steg.