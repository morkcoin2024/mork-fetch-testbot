# Single source of truth: export the same Flask app object
from app import app, watch_start  # noqa: F401

# fire up background watcher in app process
try:
    watch_start()
except Exception:
    pass