"""
opencv_detect.py
────────────────
Vision Engine: OpenCV edge detection for UI element bounding boxes.

Responsibilities:
  - Load an image and run Canny edge detection
  - Find contours and filter noise (too small / full-screen)
  - Draw numbered RED bounding boxes on detected elements
  - Return an elements dictionary  { "1": [x, y, w, h], ... }
"""

import cv2
import os
import numpy as np


def detect_elements(image_path: str, output_path: str = "marked.png") -> tuple:
    """
    Run OpenCV edge detection on a screenshot.

    Draws numbered RED boxes on each detected UI element and saves the
    annotated image.

    Args:
        image_path:  Absolute path to the raw screenshot.
        output_path: Where to save the annotated (marked) image.

    Returns:
        (elements_dict, marked_image_path)
          elements_dict: { "1": [x, y, w, h], "2": [x, y, w, h], … }
          marked_image_path: absolute path to the saved annotated image
    """
    print("[VISION] Running OpenCV edge detection …")

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    img_h, img_w = img.shape[:2]

    # ── Preprocessing ─────────────────────────────────────────────────────
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # ── Canny edge detection ──────────────────────────────────────────────
    edges = cv2.Canny(blurred, 50, 150)

    # ── Dilate to close gaps ──────────────────────────────────────────────
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)

    # ── Find external contours ────────────────────────────────────────────
    contours, _ = cv2.findContours(
        dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # ── Collect and filter bounding boxes ─────────────────────────────────
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
            (0, 0, 255),
            cv2.FILLED,
        )
        cv2.putText(
            marked_img,
            label,
            (label_x + 2, label_y),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

        element_id += 1

    cv2.imwrite(output_path, marked_img)
    abs_path = os.path.abspath(output_path)
    print(f"  ✔ Detected {len(elements)} elements")
    print(f"  ✔ Annotated image saved: {abs_path}")
    return elements, abs_path
