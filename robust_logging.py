# ---- robust logging: file + ring buffer ----
import logging
import pathlib
from collections import deque
from logging.handlers import RotatingFileHandler

pathlib.Path("logs").mkdir(exist_ok=True)
LOG_FILE = "logs/app.log"


class RingBufferHandler(logging.Handler):
    """Keeps the last N formatted log lines in memory for /a_logs_tail fallback."""

    def __init__(self, capacity=12000):
        super().__init__()
        self.buffer = deque(maxlen=capacity)

    def emit(self, record):
        try:
            self.buffer.append(self.format(record))
        except Exception:
            pass


# Global ring buffer handler for fast access
_ring_buffer_handler = None


def setup_robust_logging():
    """Set up robust logging with file rotation and ring buffer"""
    global _ring_buffer_handler

    # Get ROOT logger for capturing all named loggers (including solscan)
    ROOT = logging.getLogger()
    ROOT.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Attach file handler once
    if not any(isinstance(h, RotatingFileHandler) for h in ROOT.handlers):
        fh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        ROOT.addHandler(fh)

    # Attach ring buffer handler to ROOT logger once (captures all named loggers)
    if not any(isinstance(h, RingBufferHandler) for h in ROOT.handlers):
        _ring_buffer_handler = RingBufferHandler(capacity=12000)
        _ring_buffer_handler.setFormatter(fmt)
        ROOT.addHandler(_ring_buffer_handler)

    # Ensure ring buffer handler is attached to ROOT logger
    if _ring_buffer_handler and not any(h is _ring_buffer_handler for h in ROOT.handlers):
        ROOT.addHandler(_ring_buffer_handler)

    logging.info("Boot logging ready: file=%s + ring-buffer", LOG_FILE)


def get_ring_buffer_lines(n_lines=50, level_filter="all"):
    """Get recent lines from ring buffer with optional level filtering"""
    global _ring_buffer_handler

    if not _ring_buffer_handler:
        return []

    # Level filtering function
    def get_log_level(line):
        line_lower = line.lower()
        if "[error]" in line_lower:
            return 40
        elif "[warning]" in line_lower or "[warn]" in line_lower:
            return 30
        elif "[info]" in line_lower:
            return 20
        return 10

    # Level thresholds
    level_thresholds = {"error": 40, "warn": 30, "warning": 30, "info": 20, "all": 0}
    min_level = level_thresholds.get(level_filter, 0)

    # Get lines from ring buffer
    lines = list(_ring_buffer_handler.buffer)

    # Filter by level if specified
    if level_filter != "all":
        lines = [line for line in lines if get_log_level(line) >= min_level]

    # Return the most recent n_lines
    return lines[-n_lines:] if lines else []


def get_ring_buffer_stats():
    """Get ring buffer statistics"""
    global _ring_buffer_handler

    if not _ring_buffer_handler:
        return {"available": False}

    return {
        "available": True,
        "current_size": len(_ring_buffer_handler.buffer),
        "max_capacity": _ring_buffer_handler.buffer.maxlen,
        "usage_percent": round(
            len(_ring_buffer_handler.buffer) / (_ring_buffer_handler.buffer.maxlen or 1) * 100, 1
        ),
    }


# Initialize logging when module is imported
setup_robust_logging()
