#!/usr/bin/env python3
"""
WSGI entry point for gunicorn
Ensures proper Flask application loading
"""

import logging
import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

try:
    # Import and expose the Flask application
    from app import app as application

    # Verify application is callable
    if not callable(application):
        raise RuntimeError("Application is not callable")

    logging.info("WSGI: Flask application loaded successfully")

except ImportError as e:
    logging.error(f"WSGI: Failed to import Flask application: {e}")
    raise
except Exception as e:
    logging.error(f"WSGI: Error loading application: {e}")
    raise

# For debugging
if __name__ == "__main__":
    application.run(debug=True, host="0.0.0.0", port=5000)
