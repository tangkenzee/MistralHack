"""
test_session.py
───────────────
Integration test for the multi-step Session feature.

Simulates a 2-step "forgot password" flow:
  Step 1: Screenshot → session.next_step(screenshot, "I forgot my password")
  Step 2: New screenshot → session.next_step(new_screenshot)  (no prompt)

Run:
  python test_session.py
"""

import os
import time
import json
import mss
from ai_brain import create_session

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(PROJECT_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

SAMPLE_PROMPT = "I can't remember my password"


def take_screenshot(name: str = "raw") -> str:
    """Capture the primary monitor and save as images/{name}.png."""
    path = os.path.join(IMAGES_DIR, f"{name}.png")
    print(f"[TEST] Taking screenshot → {path}")
    with mss.mss() as sct:
        sct.shot(output=path)
    print(f"  ✔ Saved: {path}")
    return path


def main():
    print("=" * 60)
    print("  Session — Multi-Step Integration Test")
    print("=" * 60)

    session = create_session()

    # ── Countdown ─────────────────────────────────────────────────────────
    print("\nSwitch to the target window (e.g. test_page.html in browser).")
    print("Screenshot in 5 seconds …\n")
    for i in range(5, 0, -1):
        print(f"  {i}…")
        time.sleep(1)

    # ── STEP 1: First screenshot + user prompt ────────────────────────────
    start = time.time()
    screenshot_1 = take_screenshot("raw_step1")

    print("\n" + "─" * 60)
    print(f"  STEP 1 — Prompt: \"{SAMPLE_PROMPT}\"")
    print("─" * 60 + "\n")

    result_1 = session.next_step(screenshot_1, SAMPLE_PROMPT)
    print("\n[RESULT] Step 1 →")
    print(json.dumps(result_1, indent=2, ensure_ascii=False))

    # ── Pause — in a real app the user clicks, screen changes ─────────────
    print("\n" + "=" * 60)
    print("  Now switch to the NEXT screen state")
    print("  (e.g. click the highlighted element, or open a new page)")
    print("  Screenshot in 10 seconds …")
    print("=" * 60 + "\n")
    for i in range(10, 0, -1):
        print(f"  {i}…")
        time.sleep(1)

    # ── STEP 2: New screenshot, NO user prompt (session auto-context) ─────
    screenshot_2 = take_screenshot("raw_step2")

    print("\n" + "─" * 60)
    print("  STEP 2 — No prompt (session continues with context)")
    print("─" * 60 + "\n")

    result_2 = session.next_step(screenshot_2)
    print("\n[RESULT] Step 2 →")
    print(json.dumps(result_2, indent=2, ensure_ascii=False))

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"  ✔ Test complete — {session.step} steps, {elapsed:.1f}s total")
    print(f"  Message history length: {len(session.messages)} messages")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
