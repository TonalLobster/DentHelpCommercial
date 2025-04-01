# DentalScribe AI

A Flask-based web application for dental professionals to transcribe and summarize patient consultations.

## Features

- Audio recording and upload functionality
- Transcription of dental consultations using OpenAI's Whisper API
- AI-powered summaries of consultations with structured data extraction
- Secure user authentication with license number verification
- Responsive design with Tailwind CSS and Alpine.js

## Tech Stack

- **Backend**: Flask, SQLAlchemy, Flask-Migrate, Gunicorn
- **Frontend**: Tailwind CSS, Alpine.js, Jinja2 templates
- **Database**: PostgreSQL (Heroku Postgres)
- **Authentication**: Flask-Login
- **Deployment**: Heroku

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/dental-scribe-ai.git
   cd dental-scribe-ai
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   # Edit .env and add your configuration values
   ```

5. Initialize the database:
   ```bash
   flask db upgrade
   ```

6. Run the development server:
   ```bash
   flask run
   ```

## Deployment to Heroku

1. Create a Heroku app:
   ```bash
   heroku create dental-scribe-ai
   ```

2. Add PostgreSQL:
   ```bash
   heroku addons:create heroku-postgresql:mini
   ```

3. Configure environment variables:
   ```bash
   heroku config:set OPENAI_API_KEY=your_key SECRET_KEY=your_secret_key
   ```

4. Deploy:
   ```bash
   git push heroku main
   ```

5. Run migrations:
   ```bash
   heroku run flask db upgrade
   ```

## License

[Your License]

## Contact

[Your Contact Information]
