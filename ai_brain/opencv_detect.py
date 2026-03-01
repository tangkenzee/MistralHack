"""
opencv_detect.py
────────────────
Vision Engine: OpenCV edge detection for UI element bounding boxes.

Responsibilities:
  - Load an image and run Canny edge detection
  - Find contours (including nested ones) and filter noise
  - Apply Non-Maximum Suppression to remove duplicate/overlapping boxes
  - Draw numbered RED bounding boxes on detected elements
  - Return an elements dictionary  { "1": [x, y, w, h], ... }
"""

import cv2
import os
import numpy as np


def _nms_boxes(boxes: list[list[int]], overlap_thresh: float = 0.45) -> list[int]:
    """Non-Maximum Suppression on bounding boxes [x, y, w, h].

    Returns indices of boxes to keep.
    """
    if not boxes:
        return []

    bbs = np.array(boxes, dtype=np.float32)
    x1 = bbs[:, 0]
    y1 = bbs[:, 1]
    x2 = bbs[:, 0] + bbs[:, 2]
    y2 = bbs[:, 1] + bbs[:, 3]
    areas = bbs[:, 2] * bbs[:, 3]

    # Sort by area (prefer larger, more likely to be real UI elements)
    order = areas.argsort()[::-1]
    keep = []

    while order.size > 0:
        i = order[0]
        keep.append(int(i))

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        # Suppress if IoU OR containment ratio is high
        iou = inter / np.minimum(areas[i], areas[order[1:]])

        remaining = np.where(iou <= overlap_thresh)[0]
        order = order[remaining + 1]

    return keep


def detect_elements(image_path: str, output_path: str = "marked.png") -> tuple:
    """
    Run OpenCV edge detection on a screenshot.

    Uses RETR_TREE to capture nested UI elements (buttons inside panels,
    links inside content areas, etc.), applies size filters and NMS to
    remove noise and duplicates, then draws numbered RED boxes.

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
    screen_area = img_h * img_w

    # ── Preprocessing ─────────────────────────────────────────────────────
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # ── Canny edge detection ──────────────────────────────────────────────
    edges = cv2.Canny(blurred, 50, 150)

    # ── Dilate to close gaps ──────────────────────────────────────────────
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)

    # ── Find ALL contours (including nested children) ─────────────────────
    contours, _ = cv2.findContours(
        dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    # ── Collect and filter bounding boxes ─────────────────────────────────
    raw_boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)

        # Skip noise: too small
        if w < 20 or h < 15:
            continue

        # Skip containers: too large (covers >40% of screen area)
        if (w * h) > screen_area * 0.4:
            continue

        # Skip very wide containers (>80% of screen width AND >12% height)
        if w > img_w * 0.80 and h > img_h * 0.12:
            continue

        raw_boxes.append([x, y, w, h])

    # ── Non-Maximum Suppression to deduplicate overlapping boxes ──────────
    keep_indices = _nms_boxes(raw_boxes, overlap_thresh=0.45)
    filtered_boxes = [raw_boxes[i] for i in keep_indices]

    # ── Sort top-to-bottom, left-to-right ─────────────────────────────────
    sorted_boxes = sorted(filtered_boxes, key=lambda b: (b[1], b[0]))

    # ── Draw and register ─────────────────────────────────────────────────
    marked_img = img.copy()
    elements = {}

    for element_id, (x, y, w, h) in enumerate(sorted_boxes, start=1):
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

    cv2.imwrite(output_path, marked_img)
    abs_path = os.path.abspath(output_path)
    print(f"  ✔ Detected {len(elements)} elements")
    print(f"  ✔ Annotated image saved: {abs_path}")
    return elements, abs_path
