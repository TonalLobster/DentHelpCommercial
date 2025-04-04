"""
Custom Jinja filters for the DentalScribe application.
"""
import json
from datetime import datetime

def register_filters(app):
    """Register custom filters with the Flask application."""
    
    @app.template_filter('format_date')
    def format_date(value, format='%Y-%m-%d'):
        """Format a datetime object to string."""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        return value.strftime(format)
    
    @app.template_filter('format_datetime')
    def format_datetime(value, format='%Y-%m-%d %H:%M'):
        """Format a datetime object to string with time."""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        return value.strftime(format)
    
    @app.template_filter('parse_json')
    def parse_json(value):
        """Parse a JSON string to a Python object."""
        if not value:
            return {}
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    @app.template_filter('tojson_pretty')
    def tojson_pretty(value):
        """Convert a Python object to a pretty-printed JSON string."""
        return json.dumps(value, indent=2, ensure_ascii=False)
    
    @app.template_filter('highlight_teeth')
    def highlight_teeth(text):
        """Highlight teeth numbers in the text (e.g., 11, 12, etc.)."""
        if not text:
            return ""
        
        # Simple highlighting with span tags - can be enhanced with regex
        for i in range(11, 49):
            # Skip non-existent teeth numbers
            if i > 18 and i < 21:
                continue
            if i > 28 and i < 31:
                continue
            if i > 38 and i < 41:
                continue
            if i > 48:
                continue
                
            # Replace with span
            text = text.replace(
                f" {i} ", 
                f' <span class="badge-dental">{i}</span> '
            )
        
        # Also highlight quadrants
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            text = text.replace(
                f" {q} ", 
                f' <span class="badge-dental">{q}</span> '
            )
            
        return text