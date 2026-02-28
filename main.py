"""
main.py
───────
ClearPath — Main application entry point.

Hotkey-driven session loop (per SSOT §3 architecture):
  F9   → Take screenshot  → run AI pipeline (next step)
  F10  → Reset session     → clear history, start new prompt chain
  Esc  → Exit application

The session runs indefinitely until reset (F10) or exit (Esc).
No hardcoded timers or fixed step counts.
"""

import os
import json
import keyboard
import mss
from ai_brain import create_session

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(PROJECT_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

SAMPLE_PROMPT = "I can't remember my password"

# ── State ─────────────────────────────────────────────────────────────────────
session = create_session()
prompt = SAMPLE_PROMPT   # Used on first step; None for follow-ups
processing = False       # Guard against overlapping AI calls


# ── Screenshot ────────────────────────────────────────────────────────────────
def take_screenshot() -> str:
    """Capture the primary monitor → images/raw_step{n}.png."""
    step = session.step + 1  # next step number (step increments inside next_step)
    path = os.path.join(IMAGES_DIR, f"raw_step{step}.png")
    with mss.mss() as sct:
        sct.shot(output=path)
    print(f"  📸 Screenshot saved: {path}")
    return path


# ── Hotkey Callbacks ──────────────────────────────────────────────────────────
def on_next_step():
    """F9 — Capture screen and run the AI pipeline for the next step."""
    global prompt, processing

    if processing:
        print("  ⏳ Still processing previous step — please wait.")
        return

    processing = True
    try:
        step_num = session.step + 1
        print(f"\n{'─' * 60}")
        print(f"  ▶ F9 pressed — Running Step {step_num}")
        print(f"{'─' * 60}")

        screenshot = take_screenshot()

        if prompt:
            print(f"  💬 Prompt: \"{prompt}\"")
        else:
            print(f"  💬 Auto-continuing session (no new prompt)")

        result = session.next_step(screenshot, prompt)
        print(f"\n[RESULT] Step {session.step} →")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # After first step, clear the prompt so follow-ups auto-continue
        prompt = None

    except Exception as e:
        print(f"  ❌ Error: {e}")
    finally:
        processing = False


def on_reset():
    """F10 — Reset the session and prepare for a new prompt chain."""
    global prompt, processing

    processing = False
    session.reset()
    prompt = SAMPLE_PROMPT

    print(f"\n{'=' * 60}")
    print(f"  🔄 Session reset — ready for new task")
    print(f"  Next F9 will start fresh with: \"{SAMPLE_PROMPT}\"")
    print(f"{'=' * 60}\n")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  ClearPath — Hotkey Session Controller")
    print("=" * 60)
    print()
    print("  Hotkeys:")
    print("  alt + n   → Take screenshot & run AI (next step)")
    print("  alt + r  → Reset session")
    print("  Esc  → Exit")
    print()
    print(f"  Initial prompt: \"{SAMPLE_PROMPT}\"")
    print()
    print("  Switch to your target window, then press alt + n to begin.")
    print("─" * 60)

    keyboard.add_hotkey("alt+n", on_next_step, suppress=True)
    keyboard.add_hotkey("alt+r", on_reset, suppress=True)

    # Block until Esc is pressed
    keyboard.wait("esc")

    print(f"\n{'=' * 60}")
    print(f"  👋 Exiting ClearPath. Goodbye!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
