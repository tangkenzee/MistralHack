"""
mistral_label.py
────────────────
Reasoning Engine: VLM integration for UI element analysis.

Supports two providers (chosen via .env):
  • Mistral — default provider
  • Gemini  — used only when AI_PROVIDER=gemini is set in .env

Responsibilities:
  - Encode annotated screenshots to base64
  - Send images + user prompts to the chosen VLM API
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
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed — parse .env manually
    import pathlib
    _env_path = pathlib.Path(__file__).parent.parent / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text().splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

# ── Provider SDKs (imported lazily; only the active one is needed) ────────────
try:
    from mistralai import Mistral
except ImportError:
    Mistral = None

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

# import prompt.txt to replace the TARGET system prompt
_PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt.txt")
with open(_PROMPT_PATH, "r") as f:
    TARGET_SYSTEM_PROMPT = f.read()

# ── Load environment ──────────────────────────────────────────────────────────
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
GOOGLE_API_KEY  = os.getenv("GOOGLE_API_KEY", "")

# Determine which provider to use: Mistral by default, Gemini only if explicitly set
_provider_override = os.getenv("AI_PROVIDER", "").lower().strip()
if _provider_override == "gemini" and GOOGLE_API_KEY:
    AI_PROVIDER = "gemini"
else:
    AI_PROVIDER = "mistral"

# ── Model Configuration ──────────────────────────────────────────────────────
MISTRAL_MODEL_CONFIG = {
    "model": "mistral-small-latest",
    "temperature": 0.2,
    "response_format": {"type": "json_object"},
}

GEMINI_MODEL = "gemini-3-flash-preview"


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
    """Return True if a valid-looking API key is configured for the active provider."""
    if AI_PROVIDER == "gemini":
        if not GOOGLE_API_KEY:
            print("  ⚠ GOOGLE_API_KEY not set — skipping Gemini call.")
            return False
    else:
        if not MISTRAL_API_KEY or MISTRAL_API_KEY == "your_mistral_api_key_here":
            print("  ⚠ MISTRAL_API_KEY not set — skipping Mistral call.")
            return False
    return True


# ── Core LLM Call (shared by one-shot & session modes) ────────────────────────

def _call_gemini(messages: list[dict]) -> str:
    """Convert OpenAI-style messages to Gemini SDK calls and return response text."""
    if genai is None:
        print("  ⚠ google-genai not installed.")
        return ""

    client = genai.Client(api_key=GOOGLE_API_KEY)

    # Extract system prompt from messages
    system_prompt = ""
    conversation_parts = []
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
        else:
            content = msg["content"]
            if isinstance(content, str):
                conversation_parts.append(genai_types.Part.from_text(text=content))
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            conversation_parts.append(genai_types.Part.from_text(text=part["text"]))
                        elif part.get("type") == "image_url":
                            url = part.get("image_url", "")
                            if isinstance(url, str) and url.startswith("data:"):
                                header, b64data = url.split(",", 1)
                                mime = header.split(";")[0].split(":")[1]
                                img_bytes = base64.b64decode(b64data)
                                conversation_parts.append(
                                    genai_types.Part.from_bytes(data=img_bytes, mime_type=mime)
                                )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=conversation_parts,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None,
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    return response.text.strip()


def _call_mistral_api(messages: list[dict]) -> str:
    """Send a full messages list to Mistral and return the raw response text."""
    if Mistral is None:
        print("  ⚠ mistralai not installed.")
        return ""

    client = Mistral(api_key=MISTRAL_API_KEY)
    response = client.chat.complete(**MISTRAL_MODEL_CONFIG, messages=messages)
    return response.choices[0].message.content.strip()


def _call_llm(messages: list[dict]) -> str:
    """Route to the active provider. This is the single point of contact used
    by both one-shot functions and the multi-step Session class."""
    if not _check_api_key():
        return ""

    if AI_PROVIDER == "gemini":
        return _call_gemini(messages)
    return _call_mistral_api(messages)


# Keep backward-compat alias so session.py import doesn't break
_call_mistral = _call_llm


# ── Public Functions ──────────────────────────────────────────────────────────

def label_elements(marked_image_path: str) -> list:
    """
    Send the annotated image to Mistral and get a description of EVERY
    numbered box (diagnostic / reporting mode).

    Returns a list of dicts:
      [{ "box_id": 1, "type": "button", "text_content": "Submit", "purpose": "..." }, ...]
    """
    print(f"[BRAIN] Sending annotated image to {AI_PROVIDER} for labeling …")

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

    raw = _call_llm(messages)
    if not raw:
        return []

    print(f"  \u2714 {AI_PROVIDER} responded ({len(raw)} chars)")

    labels = _parse_json(raw)
    if labels is None:
        print(f"  ⚠ Could not parse {AI_PROVIDER} response as JSON.")
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
    print(f"[BRAIN] Asking {AI_PROVIDER} which element to click …")

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

    raw = _call_llm(messages)
    if not raw:
        return {"box_id": None, "message": "API key not configured."}

    print(f"  \u2714 {AI_PROVIDER} responded ({len(raw)} chars)")

    result = _parse_json(raw)
    if result is None:
        print(f"  ⚠ Could not parse {AI_PROVIDER} response as JSON.")
        print(f"  Raw response:\n{raw}")
        return {"box_id": None, "message": "Failed to parse AI response."}

    return result

