"""
ai_brain.py
───────────
Orchestrator: The single entry-point for the AI logic layer.

This module is the "Server" side of the ClearPath architecture (per SSOT §3).
The overlay UI only ever calls `get_target_coordinates()` from this file.

Pipeline:
  1. OpenCV vision pass  →  opencv_detect.detect_elements()
  2. Mistral reasoning   →  mistral_label.find_target_box()
  3. Coordinate lookup   →  map box ID → [x, y, w, h]
  4. Return the SSOT-guaranteed output schema to the UI
"""

import os
from ai_brain.opencv_detect import detect_elements
from ai_brain.mistral_label import find_target_box, label_elements
from ai_brain.session import Session

# ── Images output directory (project root / images) ──────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(_PROJECT_ROOT, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)


def get_target_coordinates(screenshot_path: str, user_prompt: str) -> dict:
    """
    Main entry-point called by overlay_ui.py.

    Takes a raw screenshot and a user prompt, runs the full
    OpenCV → Mistral pipeline, and returns the target element's
    coordinates + a friendly message.

    Args:
        screenshot_path: Absolute path to the raw screenshot (e.g. raw.png).
        user_prompt:     The user's natural-language request
                         (e.g. "I can't remember my password").

    Returns:
        Guaranteed Output Schema (per SSOT §4):
        {
            "status":  "success" | "error",
            "x":       int,
            "y":       int,
            "width":   int,
            "height":  int,
            "message": str
        }
    """
    print("=" * 60)
    print("  ClearPath — AI Brain Processing")
    print("=" * 60)

    # ── Step 1: OpenCV vision pass ────────────────────────────────────────
    try:
        # Save marked image into the images/ directory
        marked_path = os.path.join(IMAGES_DIR, "marked.png")

        elements, marked_path = detect_elements(screenshot_path, marked_path)

        print(elements)
    except FileNotFoundError as e:
        return {
            "status": "error",
            "x": 0, "y": 0, "width": 0, "height": 0,
            "message": f"Vision engine failed: {e}",
        }

    if not elements:
        return {
            "status": "error",
            "x": 0, "y": 0, "width": 0, "height": 0,
            "message": "No UI elements were detected on screen.",
        }

    # ── Step 2: Mistral reasoning pass ────────────────────────────────────
    result = find_target_box(marked_path, user_prompt)
    box_id = result.get("box_id")
    ai_message = result.get("message", "")

    # ── Step 3: Map box ID → coordinates ──────────────────────────────────
    if box_id is None:
        return {
            "status": "error",
            "x": 0, "y": 0, "width": 0, "height": 0,
            "message": ai_message or "Could not determine the target element.",
        }

    str_id = str(box_id)
    if str_id not in elements:
        return {
            "status": "error",
            "x": 0, "y": 0, "width": 0, "height": 0,
            "message": f"Mistral returned box #{box_id} but it was not found in OpenCV results.",
        }

    x, y, w, h = elements[str_id]
    print(f"This is the target ID: {str_id}")

    # ── Step 4: Return SSOT-guaranteed schema ─────────────────────────────
    return {
        "status": "success",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "message": ai_message,
    }


def get_all_element_labels(screenshot_path: str) -> dict:
    """
    Diagnostic / reporting helper.

    Runs the full OpenCV → Mistral labeling pipeline and returns a merged
    report of all detected elements with their AI-generated descriptions.

    Returns:
        {
            "status": "success" | "error",
            "elements": [
                {
                    "box_id": 1,
                    "bounding_box": {"x": int, "y": int, "width": int, "height": int},
                    "type": str,
                    "text_content": str | None,
                    "purpose": str
                }, ...
            ]
        }
    """
    try:
        marked_path = os.path.join(IMAGES_DIR, "marked.png")

        elements, marked_path = detect_elements(screenshot_path, marked_path)
    except FileNotFoundError as e:
        return {"status": "error", "elements": [], "message": str(e)}

    if not elements:
        return {"status": "error", "elements": [], "message": "No elements detected."}

    labels = label_elements(marked_path)
    label_map = {str(item.get("box_id", "")): item for item in labels}

    merged = []
    for eid, coords in elements.items():
        x, y, w, h = coords
        info = label_map.get(eid, {})
        merged.append({
            "box_id": int(eid),
            "bounding_box": {"x": x, "y": y, "width": w, "height": h},
            "type": info.get("type", "unknown"),
            "text_content": info.get("text_content"),
            "purpose": info.get("purpose", "unknown"),
        })

    return {"status": "success", "elements": merged}
