"""
session.py
──────────
Multi-step navigation session with LLM conversation memory.

A Session keeps the Mistral chat `messages` list alive across steps so that
when the user clicks an element and the screen changes, the next call to
`next_step()` sends the FULL history (previous screenshots + AI replies)
and the model can reason about "what comes next."

Usage:
    session = Session()
    r1 = session.next_step("raw_step1.png", "I forgot my password")
    # … user clicks, screen changes …
    r2 = session.next_step("raw_step2.png")   # no prompt needed
"""

import os
from ai_brain.opencv_detect import detect_elements
from ai_brain.mistral_label import (
    _call_mistral,
    _encode_image_base64,
    _parse_json,
    TARGET_SYSTEM_PROMPT,
)

# ── Images output directory (project root / images) ──────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(_PROJECT_ROOT, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

# Auto-generated follow-up prompt for steps 2+
_FOLLOW_UP_PROMPT = (
    "The user has performed the action you suggested in the previous step. "
    "Here is the updated screen. Analyze carefully and decide what they should "
    "do next.\n\n"
    "- If a success or completion message is visible, congratulate them and "
    "set box_id to null."
)


class Session:
    """Stateful multi-step navigation session.

    Accumulates Mistral chat messages so the model sees every previous
    screenshot and its own previous answers when deciding the next action.
    """

    def __init__(self):
        self.messages: list[dict] = []
        self.step: int = 0

    # ── Public API ────────────────────────────────────────────────────────

    def next_step(self, screenshot_path: str, user_prompt: str | None = None) -> dict:
        """Run one iteration of the capture → detect → reason pipeline.

        Args:
            screenshot_path: Path to the NEW raw screenshot.
            user_prompt:     Required on the FIRST call (e.g. "I forgot my
                             password"). On subsequent calls it is optional —
                             the session auto-generates follow-up context.

        Returns:
            SSOT-guaranteed output schema:
            {
                "status":  "success" | "error",
                "x":       int,
                "y":       int,
                "width":   int,
                "height":  int,
                "message": str
            }
        """

        self.step += 1
        print(f"\n{'=' * 60}")
        print(f"  ClearPath Session — Step {self.step}")
        print(f"{'=' * 60}")

        # ── 1. OpenCV vision pass ─────────────────────────────────────────
        try:
            marked_path = os.path.join(IMAGES_DIR, f"marked_step{self.step}.png")
            elements, marked_path = detect_elements(screenshot_path, marked_path)
            print(f"  Detected {len(elements)} elements")
        except FileNotFoundError as e:
            return self._error(f"Vision engine failed: {e}")

        if not elements:
            return self._error("No UI elements were detected on screen.")

        # ── 2. Build the user message for this step ───────────────────────
        #   Send BOTH the raw screenshot (clean UI) and the marked screenshot
        #   (with red boxes + IDs) so the model can cross-reference actual
        #   element appearance with numbered IDs for accurate targeting.
        raw_b64 = _encode_image_base64(screenshot_path)
        marked_b64 = _encode_image_base64(marked_path)

        if self.step == 1:
            # First step: inject system prompt + user's original request
            prompt_text = user_prompt or "Help me navigate this screen."
            self.messages.append(
                {"role": "system", "content": TARGET_SYSTEM_PROMPT}
            )
        else:
            # Follow-up steps: use auto-context or an explicit override
            prompt_text = user_prompt or _FOLLOW_UP_PROMPT

        self.messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": f"data:image/png;base64,{raw_b64}",
                },
                {
                    "type": "image_url",
                    "image_url": f"data:image/png;base64,{marked_b64}",
                },
                {
                    "type": "text",
                    "text": prompt_text,
                },
            ],
        })

        # ── 3. Mistral reasoning pass (full history) ──────────────────────
        raw = _call_mistral(self.messages)
        print(f"  ✔ Mistral responded ({len(raw)} chars)")

        result = _parse_json(raw)
        if result is None:
            print(f"  ⚠ Could not parse Mistral response as JSON.\n  Raw: {raw}")
            return self._error("Failed to parse AI response.")

        # Append the assistant reply to history for future steps
        self.messages.append({"role": "assistant", "content": raw})

        # ── 4. Map box ID → coordinates ───────────────────────────────────
        box_id = result.get("box_id")
        ai_message = result.get("message", "")

        if box_id is None:
            return self._error(ai_message or "Could not determine the target element.")

        str_id = str(box_id)
        if str_id not in elements:
            return self._error(
                f"Mistral returned box #{box_id} but it was not found in "
                f"OpenCV results."
            )

        x, y, w, h = elements[str_id]
        print(f"  Target element: box #{str_id} at ({x}, {y}, {w}, {h})")

        return {
            "status": "success",
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "message": ai_message,
        }

    def reset(self):
        """Clear conversation history and start fresh."""
        self.messages.clear()
        self.step = 0
        print("[Session] Reset — history cleared.")

    # ── Internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _error(message: str) -> dict:
        return {
            "status": "error",
            "x": 0, "y": 0, "width": 0, "height": 0,
            "message": message,
        }
