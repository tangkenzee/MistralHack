"""
test_ai_brain.py
────────────────
Quick test to verify the ai_brain pipeline end-to-end.

Steps:
  1. Takes a screenshot (5-second countdown so you can switch windows)
  2. Runs get_target_coordinates() with a sample prompt
  3. Runs get_all_element_labels() for a full diagnostic report
  4. Prints results
"""

import os
import time
import json
import mss
from ai_brain import get_target_coordinates, get_all_element_labels

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(PROJECT_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)
RAW_PATH = os.path.join(IMAGES_DIR, "raw.png")
SAMPLE_PROMPT = "I can't remember my password"


def take_screenshot() -> str:
    """Capture the primary monitor and save as raw.png."""
    print("[TEST] Taking screenshot …")
    with mss.mss() as sct:
        sct.shot(output=RAW_PATH)
    print(f"  ✔ Saved: {RAW_PATH}")
    return RAW_PATH


def main():
    print("=" * 60)
    print("  ai_brain — Integration Test")
    print("=" * 60)

    
    # ── Countdown ─────────────────────────────────────────────────────────
    print("\nSwitch to the target window (e.g. test_page.html in browser).")
    print("Screenshot in 5 seconds …\n")
    for i in range(5, 0, -1):
        print(f"  {i}…")
        time.sleep(1)

    # ── 1. Screenshot ─────────────────────────────────────────────────────
    start_time = time.time()
    screenshot = take_screenshot()

    # ── 2. Test get_target_coordinates (navigation mode) ──────────────────
    print("\n" + "─" * 60)
    print(f"  Testing get_target_coordinates()")
    print(f"  Prompt: \"{SAMPLE_PROMPT}\"")
    print("─" * 60 + "\n")

    result = get_target_coordinates(screenshot, SAMPLE_PROMPT)
    print("\n[RESULT] get_target_coordinates →")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # # ── 3. Test get_all_element_labels (diagnostic mode) ──────────────────
    # print("\n" + "─" * 60)
    # print("  Testing get_all_element_labels()")
    # print("─" * 60 + "\n")

    # report = get_all_element_labels(screenshot)
    # print(f"\n[RESULT] get_all_element_labels → {len(report.get('elements', []))} elements")
    # print(json.dumps(report, indent=2, ensure_ascii=False))

    # # ── 4. Save report to file ────────────────────────────────────────────
    # report_path = os.path.join(OUTPUT_DIR, "test_report.json")
    # with open(report_path, "w", encoding="utf-8") as f:
    #     json.dump(report, f, indent=2, ensure_ascii=False)
    # print(f"\n✔ Full report saved to: {report_path}")
    # print("✔ Test complete.")

    print(f"\n time spent: {time.time() - start_time}")

if __name__ == "__main__":
    main()
