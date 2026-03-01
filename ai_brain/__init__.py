"""
ai_brain package
────────────────
Re-export the public API so callers can do:

    from ai_brain import get_target_coordinates
    from ai_brain import get_all_element_labels
    from ai_brain import create_session, Session
    from ai_brain import realtime_transcribe
    from ai_brain import speak, stop_speaking
"""

from ai_brain.ai_brain import get_target_coordinates, get_all_element_labels
from ai_brain.session import Session
from ai_brain.speech_to_text import realtime_transcribe
from ai_brain.text_to_speech import speak, stop_speaking

__all__ = [
    "get_target_coordinates",
    "get_all_element_labels",
    "Session",
    "realtime_transcribe",
    "speak",
    "stop_speaking",
]


def create_session() -> Session:
    """Create a new multi-step navigation session."""
    return Session()
