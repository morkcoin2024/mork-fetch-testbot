#!/usr/bin/env python3
"""
Simple main.py for gunicorn WSGI compatibility
Directly imports and exposes the Flask app
"""

# Import the Flask application
from app import app

# Export for gunicorn
application = app

# For direct execution
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)