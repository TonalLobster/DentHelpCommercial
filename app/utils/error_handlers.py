"""
Error handlers for the Flask application.
"""
from flask import render_template

def register_error_handlers(app):
    """Register error handlers for the application."""
    
    @app.errorhandler(400)
    def bad_request(e):
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403
        
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
        
    @app.errorhandler(413)
    def request_entity_too_large(e):
        return render_template('errors/413.html', max_size='100MB'), 413
        
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error(f"Unhandled exception: {str(e)}")
        return render_template('errors/500.html'), 500