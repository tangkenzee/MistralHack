"""
tests/conftest.py
=================
Shared pytest configuration and fixtures for the Halo test suite.

Adds the project root to sys.path so `overlay_ui` and `ai_brain` are
importable without an installed package.  All Qt-requiring tests receive
the `qtbot` fixture automatically via pytest-qt.
"""

import sys
from pathlib import Path

import pytest

# ── Make the project root importable ─────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ── Shared data fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def success_result() -> dict:
    """
    A canonical SSOT-compliant success response dict.
    Use this whenever you need a valid ai_brain return value.
    """
    return {
        "status":  "success",
        "x":       380,
        "y":       450,
        "width":   150,
        "height":  30,
        "message": "Click the highlighted button.",
    }


@pytest.fixture
def error_result() -> dict:
    """
    A canonical SSOT-compliant error response dict.
    """
    return {
        "status":  "error",
        "x":       0,
        "y":       0,
        "width":   0,
        "height":  0,
        "message": "Sorry, I could not find anything to highlight.",
    }
