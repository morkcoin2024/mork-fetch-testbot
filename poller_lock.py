# poller_lock.py
import atexit
import os

_PLOCK_PATH = os.environ.get("MORK_POLLER_LOCK", "/tmp/mork_poller.lock")
_FD = None


def acquire() -> bool:
    """Return True if we create the lock (we are the poller), else False."""
    global _FD
    try:
        _FD = os.open(_PLOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(_FD, str(os.getpid()).encode())
        atexit.register(release)
        return True
    except FileExistsError:
        return False


def release():
    """Best-effort release."""
    global _FD
    try:
        if _FD is not None:
            os.close(_FD)
            _FD = None
        if os.path.exists(_PLOCK_PATH):
            os.unlink(_PLOCK_PATH)
    except Exception:
        pass
