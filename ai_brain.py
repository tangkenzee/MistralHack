"""
Halo - ai_brain.py
========================
AI + Vision "Server" layer. Owned by the AI/backend developer.
overlay_ui.py calls ONLY the public function below — never touches
Mistral or OpenCV directly.

Current state: STUB — returns a fake but schema-valid response so the
UI layer can be developed and tested independently.
"""


def get_target_coordinates(screenshot_path: str, user_prompt: str) -> dict:
    """
    Given a path to a screenshot and the user's natural-language request,
    identify the on-screen element the user needs to interact with and
    return its coordinates plus an empathetic guidance message.

    Parameters
    ----------
    screenshot_path : str
        Absolute or relative path to the raw screenshot (e.g. "raw.png").
    user_prompt : str
        The user's natural-language input (e.g. "I can't remember my password").

    Returns
    -------
    dict — always matches the SSOT schema:
        {
            "status":  "success" | "error",
            "x":       int,   # left edge of target element (screen coords)
            "y":       int,   # top edge of target element (screen coords)
            "width":   int,   # width of target element
            "height":  int,   # height of target element
            "message": str,   # empathetic guidance shown to the user
        }
    """
    # ── STUB ──────────────────────────────────────────────────────────────────
    # TODO (AI dev): replace this block with:
    #   1. OpenCV vision pass on `screenshot_path`  → detect & label UI shapes
    #   2. Mistral Pixtral reasoning pass            → identify correct box ID
    #   3. Map box ID back to real screen coordinates
    # ─────────────────────────────────────────────────────────────────────────
    print(f"[ai_brain] stub called | screenshot={screenshot_path!r} | prompt={user_prompt!r}")

    return {
        "status":  "success",
        "x":       380,
        "y":       450,
        "width":   150,
        "height":  30,
        "message": (
            "Don't worry, let's reset it together. "
            "Click the 'Forgot Password' link I've highlighted for you."
        ),
    }
