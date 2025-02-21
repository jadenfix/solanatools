# core/utils.py
from datetime import datetime

def current_time():
    """Return the current UTC time."""
    return datetime.utcnow()