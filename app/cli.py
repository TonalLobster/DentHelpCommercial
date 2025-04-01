import click
from flask.cli import with_appcontext
from app import db
from app.models.user import User

def register_commands(app):
    """Register Flask CLI commands."""
    
    @app.cli.command('init-db')
    @with_appcontext
    def init_db():
        """Initialize database tables."""
        db.create_all()
        click.echo('Database tables created.')
    
    @app.cli.command('seed-db')
    @with_appcontext
    def seed_db():
        """Seed database with initial data."""
        # Check if any users exist
        if User.query.count() == 0:
            # Create admin user
            admin = User(
                username='admin',
                email='admin@example.com',
                license_number='ADMIN001'
            )
            admin.set_password('password')
            db.session.add(admin)
            
            # Create test user
            test_user = User(
                username='tandlakare',
                email='test@example.com',
                license_number='TEST001'
            )
            test_user.set_password('password')
            db.session.add(test_user)
            
            db.session.commit()
            click.echo('Database seeded with initial users.')
        else:
            click.echo('Database already contains users. Skipping seeding.')