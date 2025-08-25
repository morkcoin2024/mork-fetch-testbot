#!/bin/bash
# Force one process/one thread so SCANNERS is shared across webhook and scanners
exec gunicorn -k gthread -w 1 --threads 1 --reload=false -b 0.0.0.0:5000 app:app
