"""
main.py - Application Entry Point
"""
from app import app

if __name__ == "__main__":
    # Import app and run
    app.run(host='0.0.0.0', port=5000, debug=True)