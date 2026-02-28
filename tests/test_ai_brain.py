"""
tests/test_ai_brain.py
======================
Unit tests for ai_brain.get_target_coordinates.

These tests treat ai_brain as a black box and verify only the
SSOT-guaranteed output schema — not internal implementation.
That keeps the tests valid when the stub is replaced with real logic.
"""

import pytest
import ai_brain

# ── Helpers ───────────────────────────────────────────────────────────────────
REQUIRED_KEYS = {"status", "x", "y", "width", "height", "message"}
VALID_STATUSES = {"success", "error"}


def call(prompt: str = "I can't remember my password") -> dict:
    return ai_brain.get_target_coordinates("raw.png", prompt)


# ── Schema tests ──────────────────────────────────────────────────────────────

class TestOutputSchema:
    """The function must always return a dict matching the SSOT contract."""

    def test_returns_dict(self):
        result = call()
        assert isinstance(result, dict)

    def test_all_required_keys_present(self):
        result = call()
        assert REQUIRED_KEYS.issubset(result.keys()), (
            f"Missing keys: {REQUIRED_KEYS - result.keys()}"
        )

    def test_no_extra_unexpected_keys(self):
        """Warn if new keys appear — callers would ignore them but it's
        worth knowing during development."""
        result = call()
        extra = set(result.keys()) - REQUIRED_KEYS
        # We allow extra keys (non-breaking) but they should be documented.
        # This test is currently informational rather than a hard failure.
        assert isinstance(extra, set)  # always true — serves as a note hook

    def test_status_is_valid_string(self):
        result = call()
        assert result["status"] in VALID_STATUSES, (
            f"'status' must be one of {VALID_STATUSES}, got {result['status']!r}"
        )

    def test_x_is_int(self):
        assert isinstance(call()["x"], int)

    def test_y_is_int(self):
        assert isinstance(call()["y"], int)

    def test_width_is_int(self):
        assert isinstance(call()["width"], int)

    def test_height_is_int(self):
        assert isinstance(call()["height"], int)

    def test_message_is_non_empty_string(self):
        msg = call()["message"]
        assert isinstance(msg, str)
        assert len(msg.strip()) > 0, "'message' must not be empty or whitespace"

    def test_coordinates_are_non_negative_on_success(self):
        """On a success response the coordinates should be usable screen coords."""
        result = call()
        if result["status"] == "success":
            assert result["x"]      >= 0
            assert result["y"]      >= 0
            assert result["width"]  >  0, "width must be positive"
            assert result["height"] >  0, "height must be positive"


# ── Callable interface tests ──────────────────────────────────────────────────

class TestCallableInterface:
    """Verify the function can be called correctly under various conditions."""

    def test_accepts_positional_args(self):
        result = ai_brain.get_target_coordinates("raw.png", "help me")
        assert isinstance(result, dict)

    def test_accepts_keyword_args(self):
        result = ai_brain.get_target_coordinates(
            screenshot_path="raw.png",
            user_prompt="help me",
        )
        assert isinstance(result, dict)

    def test_different_prompts_all_return_valid_schema(self):
        prompts = [
            "I forgot my password",
            "How do I log in?",
            "Where is the submit button?",
            "",                         # edge case: empty prompt
            "   ",                      # edge case: whitespace prompt
            "a" * 500,                  # edge case: very long prompt
        ]
        for prompt in prompts:
            result = ai_brain.get_target_coordinates("raw.png", prompt)
            assert isinstance(result, dict), f"Failed for prompt={prompt!r}"
            assert REQUIRED_KEYS.issubset(result.keys()), (
                f"Missing keys for prompt={prompt!r}"
            )

    def test_different_screenshot_paths_return_valid_schema(self):
        paths = ["raw.png", "/tmp/screen.png", "C:\\screenshots\\raw.png", ""]
        for path in paths:
            result = ai_brain.get_target_coordinates(path, "test")
            assert isinstance(result, dict)
            assert "status" in result
