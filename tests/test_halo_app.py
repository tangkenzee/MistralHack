"""
tests/test_halo_app.py
======================
Integration tests for HaloApp — verifies that OverlayWindow,
ChatPanel, and AIWorker are wired together correctly.

All external I/O (mss screenshot, ai_brain) is patched so these tests
run fast, offline, and without touching the file system.

Requires pytest-qt (qtbot fixture).
"""

import pytest
from unittest.mock import patch, MagicMock


def _finish_typewriter(card):
    """Pump the typewriter timer until all text is revealed."""
    while card._type_pos < len(card._type_full_text):
        card._type_tick()

from overlay_ui import HaloApp, SCREENSHOT_PATH
from overlay_ui import SpotlightBar, ResponseCard, SPOTLIGHT_W, SPOTLIGHT_H, CARD_W, CARD_MIN_H, NOTCH_PEEK


@pytest.fixture
def app(qtbot):
    """
    Build a HaloApp; register all child widgets with qtbot so Qt
    cleans them up after each test.
    """
    instance = HaloApp()
    qtbot.addWidget(instance.overlay)
    qtbot.addWidget(instance.bar)
    qtbot.addWidget(instance.card)
    return instance


@pytest.fixture
def success_payload():
    return {
        "status":  "success",
        "x":       100,
        "y":       200,
        "width":   120,
        "height":  35,
        "message": "Click the link I highlighted.",
    }


@pytest.fixture
def error_payload():
    return {
        "status":  "error",
        "x":       0,
        "y":       0,
        "width":   0,
        "height":  0,
        "message": "I couldn't find that button.",
    }


# ── Construction ──────────────────────────────────────────────────────────────

class TestConstruction:
    def test_overlay_created(self, app):
        from overlay_ui import OverlayWindow
        assert isinstance(app.overlay, OverlayWindow)

    def test_card_created(self, app):
        assert isinstance(app.card, ResponseCard)

    def test_bar_created(self, app):
        assert isinstance(app.bar, SpotlightBar)

    def test_chat_is_card_alias(self, app):
        assert app.chat is app.card

    def test_worker_is_none_initially(self, app):
        assert app._worker is None

    def test_overlay_starts_hidden(self, app):
        assert not app.overlay.isVisible()

    def test_bar_starts_hidden(self, app):
        assert not app.bar.isVisible()

    def test_card_starts_hidden(self, app):
        assert not app.card.isVisible()


# ── start() ───────────────────────────────────────────────────────────────────

class TestStart:
    def test_start_shows_overlay(self, app):
        app.start()
        assert app.overlay.isVisible()

    def test_start_shows_bar(self, app):
        app.start()
        assert app.bar.isVisible()

    def test_start_shows_card(self, app):
        app.start()
        assert app.card.isVisible()

    def test_start_appends_welcome_message(self, app):
        app.start()
        _finish_typewriter(app.card)
        assert "Hello" in app.card.history.toPlainText()

    def test_start_shows_halo_as_sender(self, app):
        app.start()
        assert "Halo" in app.card.history.toHtml()


# ── _on_result — success ──────────────────────────────────────────────────────

class TestOnResultSuccess:
    def test_shows_highlight_on_overlay(self, app, success_payload):
        app._on_result(success_payload)
        from PyQt6.QtCore import QRect
        expected = QRect(
            success_payload["x"], success_payload["y"],
            success_payload["width"], success_payload["height"],
        )
        assert app.overlay._highlight == expected

    def test_appends_message_to_chat(self, app, success_payload):
        app._on_result(success_payload)
        _finish_typewriter(app.chat)
        assert success_payload["message"] in app.chat.history.toPlainText()

    def test_updates_status_to_done(self, app, success_payload):
        app._on_result(success_payload)
        assert "Act on" in app.chat.status_label.text() or "\u25b6" in app.chat.status_label.text()

    def test_highlight_coordinates_are_exact(self, app, success_payload):
        app._on_result(success_payload)
        r = app.overlay._highlight
        assert r.x()      == success_payload["x"]
        assert r.y()      == success_payload["y"]
        assert r.width()  == success_payload["width"]
        assert r.height() == success_payload["height"]


# ── _on_result — error status ─────────────────────────────────────────────────

class TestOnResultError:
    def test_does_not_show_highlight(self, app, error_payload):
        app._on_result(error_payload)
        assert app.overlay._highlight is None

    def test_appends_error_message_to_chat(self, app, error_payload):
        app._on_result(error_payload)
        _finish_typewriter(app.chat)
        assert error_payload["message"] in app.chat.history.toPlainText()

    def test_status_resets_to_ready(self, app, error_payload):
        app._on_result(error_payload)
        assert app.chat.status_label.text() == "Ready"

    def test_missing_message_key_falls_back_gracefully(self, app):
        """If 'message' key absent the UI should not crash."""
        app._on_result({"status": "error"})
        assert app.chat.status_label.text() == "Ready"


# ── _on_error ─────────────────────────────────────────────────────────────────

class TestOnError:
    def test_appends_error_text_to_chat(self, app):
        app._on_error("Connection refused")
        _finish_typewriter(app.chat)
        assert "Connection refused" in app.chat.history.toPlainText()

    def test_error_label_prefix_in_chat(self, app):
        app._on_error("timeout")
        _finish_typewriter(app.chat)
        assert "[Error]" in app.chat.history.toPlainText()

    def test_status_resets_to_ready(self, app):
        app.chat.set_status("Thinking…")
        app._on_error("something broke")
        assert app.chat.status_label.text() == "Ready"

    def test_does_not_modify_overlay_highlight(self, app):
        app.overlay.show_highlight(10, 20, 30, 40)
        app._on_error("an error")
        # _on_error must not touch the overlay
        from PyQt6.QtCore import QRect
        assert app.overlay._highlight == QRect(10, 20, 30, 40)


# ── _capture_screenshot ───────────────────────────────────────────────────────

class TestCaptureScreenshot:
    def test_calls_mss(self, app):
        mock_sct = MagicMock()
        mock_sct.monitors = [{}, {"top": 0, "left": 0, "width": 1920, "height": 1080}]

        with patch("overlay_ui.mss.mss", return_value=mock_sct) as mock_mss:
            app._capture_screenshot()

        mock_mss.assert_called_once()

    def test_calls_shot_with_correct_output_path(self, app):
        mock_sct = MagicMock()
        mock_sct.monitors = [{}, {}]

        with patch("overlay_ui.mss.mss", return_value=mock_sct):
            app._capture_screenshot()

        mock_sct.__enter__.return_value.shot.assert_called_once_with(
            mon=1, output=SCREENSHOT_PATH
        )


# ── _on_user_prompt (wiring) ──────────────────────────────────────────────────

class TestOnUserPrompt:
    def test_creates_ai_worker(self, app):
        from overlay_ui import AIWorker
        mock_sct = MagicMock()
        mock_sct.monitors = [{}, {}]

        with patch("overlay_ui.mss.mss", return_value=mock_sct):
            with patch.object(AIWorker, "start"):   # prevent real thread launch
                app._on_user_prompt("test prompt")

        assert isinstance(app._worker, AIWorker)

    def test_worker_receives_correct_prompt(self, app):
        from overlay_ui import AIWorker
        mock_sct = MagicMock()
        mock_sct.monitors = [{}, {}]

        with patch("overlay_ui.mss.mss", return_value=mock_sct):
            with patch.object(AIWorker, "start"):
                app._on_user_prompt("where is the login button?")

        assert app._worker.user_prompt == "where is the login button?"

    def test_worker_receives_screenshot_path(self, app):
        from overlay_ui import AIWorker
        mock_sct = MagicMock()
        mock_sct.monitors = [{}, {}]

        with patch("overlay_ui.mss.mss", return_value=mock_sct):
            with patch.object(AIWorker, "start"):
                app._on_user_prompt("help")

        assert app._worker.screenshot_path == SCREENSHOT_PATH
