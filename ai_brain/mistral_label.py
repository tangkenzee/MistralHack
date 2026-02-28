"""
mistral_label.py
────────────────
Reasoning Engine: Mistral AI VLM integration for UI element analysis.

Responsibilities:
  - Encode annotated screenshots to base64
  - Send images + user prompts to Mistral VLM API
  - Parse structured JSON responses
  - Two modes:
      1. label_elements()  — enumerate/describe ALL numbered boxes
      2. find_target_box()  — given a user prompt, return the single box ID
         the user should interact with (used by the main ai_brain pipeline)
"""

import os
import re
import json
import base64
from dotenv import load_dotenv
from mistralai import Mistral

# import prompt.txt to replace the TARGET system prompt
_PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt.txt")
with open(_PROMPT_PATH, "r") as f:
    TARGET_SYSTEM_PROMPT = f.read()

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# ── Model Configuration ──────────────────────────────────────────────────────
#  Centralised config for the Mistral API calls.
#    • temperature : low (0.1) for deterministic, reliable UI-navigation answers
#    • response_format : force the model to return valid JSON natively
MODEL_CONFIG = {
    "model": "mistral-small-latest",
    "temperature": 0.2,
    "response_format": {"type": "json_object"},
}


# ── System Prompts ────────────────────────────────────────────────────────────

# Prompt for labeling every box (diagnostic / reporting mode)
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

# Prompt for finding the single target box (navigation mode — per SSOT §3-4)
# TARGET_SYSTEM_PROMPT = """\
# You are a UI navigation assistant. You are looking at a screenshot of a
# computer screen. Every detectable UI element has been outlined with a numbered
# RED box.

# The user wants to accomplish a specific task. Your job is to identify which
# numbered box they should click to achieve their goal.

# You MUST reply with ONLY a valid JSON object (no markdown fences, no extra
# text) with this exact shape:

# {
#   "box_id": 14,
#   "message": "A warm, patient, encouraging message explaining what to click and why."
# }

# If you cannot determine the correct box, reply with:
# {
#   "box_id": null,
#   "message": "An apologetic message explaining that the target could not be found."
# }
# """


# ── Helpers ───────────────────────────────────────────────────────────────────

def _encode_image_base64(image_path: str) -> str:
    """Read an image file and return its base64-encoded string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _parse_json(raw: str):
    """Try to parse raw text as JSON; fall back to extracting from code fences."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try extracting a JSON array or object from markdown fences
        match = re.search(r"[\[{].*[}\]]", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        return None


def _check_api_key() -> bool:
    """Return True if a valid-looking API key is configured."""
    if not MISTRAL_API_KEY or MISTRAL_API_KEY == "your_mistral_api_key_here":
        print("  ⚠ MISTRAL_API_KEY not set — skipping Mistral call.")
        return False
    return True


# ── Core Mistral Call (shared by one-shot & session modes) ────────────────────

def _call_mistral(messages: list[dict]) -> str:
    """Send a full messages list to Mistral and return the raw response text.

    This is the single point of contact with the Mistral API, used by both
    the one-shot functions (label_elements / find_target_box) and by the
    multi-step Session class.
    """
    if not _check_api_key():
        return ""

    client = Mistral(api_key=MISTRAL_API_KEY)
    response = client.chat.complete(**MODEL_CONFIG, messages=messages)
    return response.choices[0].message.content.strip()


# ── Public Functions ──────────────────────────────────────────────────────────

def label_elements(marked_image_path: str) -> list:
    """
    Send the annotated image to Mistral and get a description of EVERY
    numbered box (diagnostic / reporting mode).

    Returns a list of dicts:
      [{ "box_id": 1, "type": "button", "text_content": "Submit", "purpose": "..." }, ...]
    """
    print("[BRAIN] Sending annotated image to Mistral AI for labeling …")

    image_b64 = _encode_image_base64(marked_image_path)

    messages = [
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
    ]

    raw = _call_mistral(messages)
    if not raw:
        return []

    print(f"  ✔ Mistral responded ({len(raw)} chars)")

    labels = _parse_json(raw)
    if labels is None:
        print("  ⚠ Could not parse Mistral response as JSON.")
        print(f"  Raw response:\n{raw}")
        return []

    return labels


def find_target_box(marked_image_path: str, user_prompt: str, raw_image_path: str | None = None) -> dict:
    """
    Send the annotated image + user prompt to Mistral and get back the
    single box ID the user should interact with (navigation mode).

    If raw_image_path is provided, both the raw (clean UI) and marked
    (annotated with box IDs) images are sent so the model can cross-reference
    the actual element appearance with the numbered IDs.

    Returns a dict:
      { "box_id": 14, "message": "Click the 'Forgot Password' link …" }

    Or on failure:
      { "box_id": None, "message": "Sorry, I could not find …" }
    """
    print("[BRAIN] Asking Mistral AI which element to click …")

    marked_b64 = _encode_image_base64(marked_image_path)

    # Build image content: raw first (if available), then marked
    image_parts = []
    if raw_image_path:
        raw_b64 = _encode_image_base64(raw_image_path)
        image_parts.append({
            "type": "image_url",
            "image_url": f"data:image/png;base64,{raw_b64}",
        })
    image_parts.append({
        "type": "image_url",
        "image_url": f"data:image/png;base64,{marked_b64}",
    })

    messages = [
        {"role": "system", "content": TARGET_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                *image_parts,
                {
                    "type": "text",
                    "text": f"The user wants to: {user_prompt}",
                },
            ],
        },
    ]

    raw = _call_mistral(messages)
    if not raw:
        return {"box_id": None, "message": "API key not configured."}

    print(f"  ✔ Mistral responded ({len(raw)} chars)")

    result = _parse_json(raw)
    if result is None:
        print("  ⚠ Could not parse Mistral response as JSON.")
        print(f"  Raw response:\n{raw}")
        return {"box_id": None, "message": "Failed to parse AI response."}

    return result

