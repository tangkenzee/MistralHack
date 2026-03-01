"""
ai_brain/text_to_speech.py
──────────────────────────
ElevenLabs Text-to-Speech integration for Halo.

All voice/model/quality settings are driven by ``tts_config.json`` in the
project root.  Edit that file to change voice, speed, stability, style,
etc. without touching any code.

Usage:
    from ai_brain.text_to_speech import speak, stop_speaking

    speak("Hello! Click the Forgot Password link.",
          on_start=lambda: print("speaking…"),
          on_done=lambda: print("done"),
          on_error=lambda e: print("err", e))

    stop_speaking()   # interrupt playback at any time
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Fallback import path ─────────────────────────────────────────────────────
_PYLIBS = os.getenv("PYLIBS_PATH", r"C:\pylibs")
if os.path.isdir(_PYLIBS) and _PYLIBS not in sys.path:
    sys.path.insert(0, _PYLIBS)

# ─── Config ───────────────────────────────────────────────────────────────────
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "tts_config.json"


def _load_config() -> dict:
    """Read tts_config.json (re-read every call so live edits take effect)."""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"  ⚠ Could not load {_CONFIG_PATH}: {exc}")
        return {}


# ─── State ────────────────────────────────────────────────────────────────────
_stop_event = threading.Event()


# ─── Public API ───────────────────────────────────────────────────────────────

def speak(
    text: str,
    *,
    on_start: callable | None = None,
    on_done: callable | None = None,
    on_error: callable | None = None,
) -> None:
    """
    Convert *text* to speech via ElevenLabs and play through speakers.

    All tuneable parameters (voice, model, speed, stability, style, etc.)
    are read from ``tts_config.json`` at call time so you can tweak them
    without restarting the app.

    This is a **blocking** call — callers should invoke it from a
    background thread / QThread.
    """
    cfg = _load_config()

    api_key = os.getenv(cfg.get("api_key_env", "ELEVENLABS_API_KEY"), "")
    if not api_key:
        if on_error:
            on_error("ELEVENLABS_API_KEY not set in .env")
        return

    _stop_event.clear()

    # Ensure ffplay is on PATH (configured in tts_config.json)
    ffplay_dir = cfg.get("ffplay_dir")
    if ffplay_dir and os.path.isdir(ffplay_dir):
        current_path = os.environ.get("PATH", "")
        if ffplay_dir not in current_path:
            os.environ["PATH"] = ffplay_dir + os.pathsep + current_path

    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs.play import play as el_play
        from elevenlabs.types import VoiceSettings

        client = ElevenLabs(api_key=api_key)

        # Build VoiceSettings from config
        vs_cfg = cfg.get("voice_settings", {})
        voice_settings = VoiceSettings(
            stability=vs_cfg.get("stability", 0.6),
            similarity_boost=vs_cfg.get("similarity_boost", 0.8),
            style=vs_cfg.get("style", 0.35),
            speed=vs_cfg.get("speed", 0.85),
            use_speaker_boost=vs_cfg.get("use_speaker_boost", True),
        )

        # Optional seed (null / missing → omit)
        seed = cfg.get("seed")

        # Optional text normalization
        normalization = cfg.get("apply_text_normalization", "auto")

        if on_start:
            on_start()

        audio = client.text_to_speech.convert(
            text=text,
            voice_id=cfg.get("voice_id", "21m00Tcm4TlvDq8ikWAM"),
            model_id=cfg.get("model_id", "eleven_flash_v2_5"),
            output_format=cfg.get("output_format", "mp3_44100_128"),
            voice_settings=voice_settings,
            apply_text_normalization=normalization,
            **({"seed": seed} if seed is not None else {}),
        )

        if _stop_event.is_set():
            return

        el_play(audio)

        if not _stop_event.is_set() and on_done:
            on_done()

    except Exception as exc:
        if on_error:
            on_error(str(exc))


def stop_speaking() -> None:
    """Signal the current playback to stop as soon as possible."""
    _stop_event.set()
