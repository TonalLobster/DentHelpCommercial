from datetime import datetime

def register_filters(app):
    """Register custom Jinja2 filters with the Flask app."""
    
    @app.template_filter('date')
    def date_filter(value, format='%Y-%m-%d'):
        """Format a date."""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return value
        return value.strftime(format)
    
    @app.template_global('now')
    def now(format='%Y-%m-%d'):
        """Return current time formatted."""
        return datetime.now().strftime(format)