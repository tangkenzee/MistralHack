"""
screenshot_parser.py
────────────────────
Test pipeline:  Screenshot → OpenCV Detection → Mistral AI Labeling

This script:
  1. Captures the screen using mss
  2. Runs OpenCV edge detection to find UI elements and draws numbered RED boxes
  3. Sends the annotated image to Mistral AI to identify and label every element
  4. Prints the results (element type, text, purpose)

No EasyOCR — uses Mistral VLM for all semantic understanding.
"""

import os
import sys
import cv2
import mss
import json
import time
import base64
import numpy as np
from dotenv import load_dotenv
from mistralai import Mistral

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = "mistral-medium-latest"


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — Screenshot
# ══════════════════════════════════════════════════════════════════════════════

def take_screenshot(filename: str = "raw.png") -> str:
    """Capture the primary monitor and return the absolute path."""
    print("[STEP 1] Taking screenshot …")
    with mss.mss() as sct:
        sct.shot(output=filename)
    abs_path = os.path.abspath(filename)
    print(f"  ✔ Saved: {abs_path}")
    return abs_path


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — OpenCV Element Detection
# ══════════════════════════════════════════════════════════════════════════════

def detect_elements(image_path: str, output_path: str = "marked.png") -> tuple:
    """
    Run OpenCV edge detection. Draws numbered RED boxes on each detected
    UI element.

    Returns (elements_dict, marked_image_path)
      elements_dict: { "1": [x, y, w, h], "2": [x, y, w, h], … }
    """
    print("[STEP 2] Running OpenCV edge detection …")

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    img_h, img_w = img.shape[:2]

    # Preprocessing
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Canny edge detection
    edges = cv2.Canny(blurred, 50, 150)

    # Dilate to close gaps
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)

    # Find external contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Collect and filter bounding boxes
    marked_img = img.copy()
    elements = {}
    element_id = 1

    bounding_boxes = [cv2.boundingRect(c) for c in contours]
    sorted_indices = sorted(
        range(len(bounding_boxes)),
        key=lambda i: (bounding_boxes[i][1], bounding_boxes[i][0]),
    )

    for idx in sorted_indices:
        x, y, w, h = bounding_boxes[idx]

        # Skip noise (too small) and full-screen boxes (too large)
        if w < 25 or h < 20:
            continue
        if w > img_w * 0.95 and h > img_h * 0.95:
            continue

        str_id = str(element_id)
        elements[str_id] = [x, y, w, h]

        # Draw RED bounding box
        cv2.rectangle(marked_img, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # Draw numbered label with filled background
        label = str_id
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55
        thickness = 2
        (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        label_x = x
        label_y = max(y - 6, th + 4)
        cv2.rectangle(
            marked_img,
            (label_x - 1, label_y - th - 4),
            (label_x + tw + 4, label_y + baseline + 2),
            (0, 0, 255), cv2.FILLED,
        )
        cv2.putText(
            marked_img, label, (label_x + 2, label_y),
            font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA,
        )

        element_id += 1

    cv2.imwrite(output_path, marked_img)
    abs_path = os.path.abspath(output_path)
    print(f"  ✔ Detected {len(elements)} elements")
    print(f"  ✔ Annotated image saved: {abs_path}")
    return elements, abs_path


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 3 — Mistral AI Labeling (replaces EasyOCR)
# ══════════════════════════════════════════════════════════════════════════════

LABEL_SYSTEM_PROMPT = """\
You are a UI element analyser. You are looking at a screenshot of a computer
screen. Every detectable UI element has been outlined with a numbered RED box.

For EACH numbered box visible in the image, describe what it is.

You MUST reply with ONLY a valid JSON array (no markdown fences, no extra text).
Each item in the array must have this exact shape:

[
  {
    "box_id": 1,
    "type": "button | text | icon | input_field | link | image | header | nav_bar | container | unknown",
    "text_content": "the visible text inside the box, or null if none",
    "purpose": "a short description of what this element does or represents"
  }
]

Be thorough — list every numbered box you can see. If a box's content is
unclear, still include it with type "unknown".
"""


def _encode_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def label_elements_with_mistral(marked_image_path: str) -> list:
    """
    Send the numbered-box annotated image to Mistral AI.
    Returns a list of dicts describing each element.
    """
    print("[STEP 3] Sending annotated image to Mistral AI for labeling …")

    if not MISTRAL_API_KEY or MISTRAL_API_KEY == "your_mistral_api_key_here":
        print("  ⚠ MISTRAL_API_KEY not set — skipping Mistral labeling.")
        return []

    client = Mistral(api_key=MISTRAL_API_KEY)
    image_b64 = _encode_image_base64(marked_image_path)

    response = client.chat.complete(
        model=MISTRAL_MODEL,
        messages=[
            {"role": "system", "content": LABEL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": f"data:image/png;base64,{image_b64}",
                    },
                    {
                        "type": "text",
                        "text": "Analyse every numbered red box in this screenshot. List each element.",
                    },
                ],
            },
        ],
    )

    raw = response.choices[0].message.content.strip()
    print(f"  ✔ Mistral responded ({len(raw)} chars)")

    # Parse JSON from the response
    try:
        labels = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON array from markdown code fences
        import re
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            labels = json.loads(match.group())
        else:
            print("  ⚠ Could not parse Mistral response as JSON.")
            print(f"  Raw response:\n{raw}")
            return []

    return labels


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 4 — Merge & Print Results
# ══════════════════════════════════════════════════════════════════════════════

def print_results(elements: dict, labels: list):
    """Merge OpenCV coordinates with Mistral labels and print a clean report."""
    # Build a lookup from box_id → Mistral label
    label_map = {}
    for item in labels:
        label_map[str(item.get("box_id", ""))] = item

    print("\n" + "=" * 80)
    print(f"  ELEMENT REPORT — {len(elements)} elements detected by OpenCV")
    if labels:
        print(f"  {len(labels)} elements labelled by Mistral AI")
    print("=" * 80)

    for eid, coords in elements.items():
        x, y, w, h = coords
        info = label_map.get(eid, {})
        el_type = info.get("type", "—")
        text = info.get("text_content", None)
        purpose = info.get("purpose", "—")

        print(f"\n  Box #{eid}")
        print(f"    Position : ({x}, {y})  Size: {w}×{h}")
        print(f"    Type     : {el_type}")
        if text:
            print(f"    Text     : \"{text}\"")
        print(f"    Purpose  : {purpose}")
        print(f"    {'─' * 50}")

    print()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN — Run the full test pipeline
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  ClearPath — Screenshot → OpenCV → Mistral AI Test")
    print("=" * 60)

    print("\nWill take a screenshot in 5 seconds …")
    print("Switch to the target window (e.g. test_page.html in browser).\n")
    for i in range(5, 0, -1):
        print(f"  {i}…")
        time.sleep(1)

    # 1. Screenshot
    raw_path = take_screenshot("raw.png")

    # 2. OpenCV detection
    elements, marked_path = detect_elements(raw_path, "marked.png")

    # 3. Mistral AI labeling
    labels = label_elements_with_mistral(marked_path)

    # 4. Print merged report
    print_results(elements, labels)

    # 5. Save full report as JSON
    report = []
    label_map = {str(l.get("box_id", "")): l for l in labels}
    for eid, coords in elements.items():
        x, y, w, h = coords
        info = label_map.get(eid, {})
        report.append({
            "box_id": int(eid),
            "bounding_box": {"x": x, "y": y, "width": w, "height": h},
            "type": info.get("type", "unknown"),
            "text_content": info.get("text_content"),
            "purpose": info.get("purpose", "unknown"),
        })

    with open("elements_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"✔ Full report saved to: {os.path.abspath('elements_report.json')}")
    print("✔ Done.")
