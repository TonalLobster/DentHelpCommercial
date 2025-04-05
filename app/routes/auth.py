"""
Authentication routes for the DentalScribe application.
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.user import User
from app import db

# Create a WTForms form for registration
class RegistrationForm(FlaskForm):
    username = StringField('Användarnamn', validators=[DataRequired()])
    email = StringField('E-post', validators=[DataRequired(), Email()])
    license_number = StringField('Tandläkar-ID', validators=[DataRequired()])
    password = PasswordField('Lösenord', validators=[DataRequired()])
    password_confirm = PasswordField('Bekräfta lösenord', 
        validators=[
            DataRequired(), 
            EqualTo('password', message='Lösenorden måste matcha')
        ])
    submit = SubmitField('Registrera')

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        if not username or not password:
            flash('Vänligen fyll i alla fält.', 'warning')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(username=username).first()
        
        # Check if user exists and password is correct
        if not user or not check_password_hash(user.password, password):
            flash('Fel användarnamn eller lösenord. Försök igen.', 'danger')
            return redirect(url_for('auth.login'))
            
        # Log in the user
        login_user(user, remember=remember)
        
        # If there is a 'next' parameter, redirect there
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
            
        flash('Inloggning lyckades!', 'success')
        return redirect(url_for('main.dashboard'))
        
    return render_template('auth/login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    # Create an instance of the registration form
    form = RegistrationForm()
    
    # Process form submission
    if form.validate_on_submit():
        # Validate license number
        valid_licenses = current_app.config.get('VALID_LICENSES', [])
        if form.license_number.data not in valid_licenses:
            flash('Ogiltigt tandläkar-ID / legitimationsnummer. Kontakta support om detta är ett fel.', 'danger')
            return redirect(url_for('auth.register'))
        
        # Check if username already exists
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            flash('Användarnamnet är redan taget. Välj ett annat.', 'danger')
            return redirect(url_for('auth.register'))
        
        # Check if email already exists
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            flash('E-postadressen används redan av ett annat konto.', 'danger')
            return redirect(url_for('auth.register'))
        
        # Create new user
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            license_number=form.license_number.data,
            password=generate_password_hash(form.password.data, method='sha256')
        )
        
        # Add user to database
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registrering lyckades! Du kan nu logga in.', 'success')
        return redirect(url_for('auth.login'))
    
    # Render the registration page with the form
    return render_template('auth/register.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    flash('Du har loggats ut.', 'info')
    return redirect(url_for('main.index'))