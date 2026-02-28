"""
tests/test_ai_worker.py
=======================
Tests for AIWorker — the QThread wrapper that calls ai_brain off the
main thread so the UI stays responsive.

Patches overlay_ui.ai_brain so we never hit real network/GPU.
Requires pytest-qt (qtbot fixture).

Note: AIWorker is a QThread, not a QWidget — never pass it to
qtbot.addWidget().  Cleanup is handled via request.addfinalizer(worker.wait)
which blocks until the thread exits before pytest tears down the test.
"""

import pytest
from unittest.mock import patch

from overlay_ui import AIWorker

SCREENSHOT = "raw.png"
PROMPT     = "I forgot my password"


@pytest.fixture
def good_result():
    return {
        "status":  "success",
        "x":       380,
        "y":       450,
        "width":   150,
        "height":  30,
        "message": "Click the highlighted link.",
    }


def _make_worker(request, screenshot=SCREENSHOT, prompt=PROMPT) -> AIWorker:
    """
    Factory: creates an AIWorker and registers a finalizer that waits
    for the thread to finish before pytest tears down the test.
    """
    worker = AIWorker(screenshot, prompt)
    request.addfinalizer(worker.wait)
    return worker


# ── Construction ──────────────────────────────────────────────────────────────

class TestConstruction:
    def test_stores_screenshot_path(self, request):
        w = _make_worker(request)
        assert w.screenshot_path == SCREENSHOT

    def test_stores_user_prompt(self, request):
        w = _make_worker(request)
        assert w.user_prompt == PROMPT

    def test_not_running_before_start(self, request):
        w = _make_worker(request)
        assert not w.isRunning()


# ── Success path ──────────────────────────────────────────────────────────────

class TestSuccessPath:
    def test_result_ready_emitted_with_correct_dict(self, qtbot, request, good_result):
        with patch("overlay_ui.ai_brain.get_target_coordinates", return_value=good_result):
            worker = _make_worker(request)
            with qtbot.waitSignal(worker.result_ready, timeout=2000) as blocker:
                worker.start()

        assert blocker.args == [good_result]

    def test_error_not_emitted_on_success(self, qtbot, request, good_result):
        with patch("overlay_ui.ai_brain.get_target_coordinates", return_value=good_result):
            worker = _make_worker(request)
            with qtbot.assertNotEmitted(worker.error):
                with qtbot.waitSignal(worker.result_ready, timeout=2000):
                    worker.start()

    def test_passes_screenshot_path_to_brain(self, qtbot, request, good_result):
        with patch(
            "overlay_ui.ai_brain.get_target_coordinates", return_value=good_result
        ) as mock_fn:
            worker = _make_worker(request, screenshot="custom_path.png")
            with qtbot.waitSignal(worker.result_ready, timeout=2000):
                worker.start()

        mock_fn.assert_called_once_with("custom_path.png", PROMPT)

    def test_passes_user_prompt_to_brain(self, qtbot, request, good_result):
        custom_prompt = "Where is the submit button?"
        with patch(
            "overlay_ui.ai_brain.get_target_coordinates", return_value=good_result
        ) as mock_fn:
            worker = _make_worker(request, prompt=custom_prompt)
            with qtbot.waitSignal(worker.result_ready, timeout=2000):
                worker.start()

        mock_fn.assert_called_once_with(SCREENSHOT, custom_prompt)

    def test_thread_finishes_after_run(self, qtbot, request, good_result):
        with patch("overlay_ui.ai_brain.get_target_coordinates", return_value=good_result):
            worker = _make_worker(request)
            with qtbot.waitSignal(worker.finished, timeout=2000):
                worker.start()

        assert not worker.isRunning()


# ── Error path ────────────────────────────────────────────────────────────────

class TestErrorPath:
    def test_error_signal_emitted_on_exception(self, qtbot, request):
        with patch(
            "overlay_ui.ai_brain.get_target_coordinates",
            side_effect=RuntimeError("Mistral API timeout"),
        ):
            worker = _make_worker(request)
            with qtbot.waitSignal(worker.error, timeout=2000) as blocker:
                worker.start()

        assert "Mistral API timeout" in blocker.args[0]

    def test_error_signal_value_is_string(self, qtbot, request):
        with patch(
            "overlay_ui.ai_brain.get_target_coordinates",
            side_effect=ValueError("bad value"),
        ):
            worker = _make_worker(request)
            with qtbot.waitSignal(worker.error, timeout=2000) as blocker:
                worker.start()

        assert isinstance(blocker.args[0], str)

    def test_result_ready_not_emitted_on_exception(self, qtbot, request):
        with patch(
            "overlay_ui.ai_brain.get_target_coordinates",
            side_effect=Exception("boom"),
        ):
            worker = _make_worker(request)
            with qtbot.assertNotEmitted(worker.result_ready):
                with qtbot.waitSignal(worker.error, timeout=2000):
                    worker.start()

    def test_thread_finishes_even_after_error(self, qtbot, request):
        with patch(
            "overlay_ui.ai_brain.get_target_coordinates",
            side_effect=Exception("crash"),
        ):
            worker = _make_worker(request)
            with qtbot.waitSignal(worker.finished, timeout=2000):
                worker.start()

        assert not worker.isRunning()
