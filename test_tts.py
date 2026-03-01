"""Quick test: speak "Halo Halo" using ElevenLabs TTS via tts_config.json."""

import os, sys

# Ensure elevenlabs can be found (fallback to C:\pylibs)
_PYLIBS = os.getenv("PYLIBS_PATH", r"C:\pylibs")
if os.path.isdir(_PYLIBS) and _PYLIBS not in sys.path:
    sys.path.insert(0, _PYLIBS)

from dotenv import load_dotenv
load_dotenv()

key = os.getenv("ELEVENLABS_API_KEY", "")
print(f"API key present: {bool(key)}  (length={len(key)})")

import shutil
print(f"ffplay found:    {shutil.which('ffplay')}")

import json
from pathlib import Path

cfg_path = Path(__file__).parent / "tts_config.json"
with open(cfg_path) as f:
    cfg = json.load(f)

print(f"Voice ID:        {cfg.get('voice_id')}")
print(f"Model:           {cfg.get('model_id')}")
print(f"Voice settings:  {cfg.get('voice_settings')}")
print()

from ai_brain.text_to_speech import speak

print("Speaking 'Halo Halo' …")
speak(
    "Halo Halo",
    on_start=lambda: print("  🔊 Playback started"),
    on_done=lambda: print("  🔊 Playback done"),
    on_error=lambda e: print(f"  ❌ Error: {e}"),
)
print("Test finished.")
