"""
tests/test_spotlight_bar.py
============================
Tests for SpotlightBar -- the notch-style input bar.

Requires pytest-qt (qtbot fixture).
"""

import pytest
from PyQt6.QtCore import Qt, QPoint

from overlay_ui import SpotlightBar, SPOTLIGHT_W, SPOTLIGHT_H, NOTCH_PEEK


@pytest.fixture
def bar(qtbot):
    b = SpotlightBar()
    qtbot.addWidget(b)
    return b


# -- Construction --------------------------------------------------------------

class TestConstruction:
    def test_fixed_width(self, bar):
        assert bar.width() == SPOTLIGHT_W

    def test_fixed_height(self, bar):
        assert bar.height() == SPOTLIGHT_H

    def test_window_flag_frameless(self, bar):
        assert bar.windowFlags() & Qt.WindowType.FramelessWindowHint

    def test_window_flag_always_on_top(self, bar):
        assert bar.windowFlags() & Qt.WindowType.WindowStaysOnTopHint

    def test_input_box_starts_empty(self, bar):
        assert bar.input_box.text() == ""

    def test_status_label_starts_ready(self, bar):
        assert bar.status_label.text() == "Ready"

    def test_starts_collapsed(self, bar):
        assert bar._expanded is False


# -- Notch expand / collapse ---------------------------------------------------

class TestNotchBehaviour:
    def test_collapsed_y_hides_most_of_bar(self, bar):
        assert bar._collapsed_y == -(SPOTLIGHT_H - NOTCH_PEEK)

    def test_expanded_y_is_zero(self, bar):
        assert bar._expanded_y == 0

    def test_initial_position_is_collapsed(self, bar):
        assert bar.y() == bar._collapsed_y

    def test_expand_sets_flag(self, bar):
        bar._expand()
        assert bar._expanded is True

    def test_collapse_sets_flag(self, bar):
        bar._expand()
        bar._collapse()
        assert bar._expanded is False

    def test_expand_when_already_expanded_is_noop(self, bar):
        bar._expand()
        bar._expand()  # should not raise
        assert bar._expanded is True

    def test_collapse_when_already_collapsed_is_noop(self, bar):
        bar._collapse()  # already collapsed
        assert bar._expanded is False

    def test_animation_target_on_expand(self, bar):
        bar._expand()
        assert bar._anim.endValue() == QPoint(bar._bar_x, bar._expanded_y)

    def test_animation_target_on_collapse(self, bar):
        bar._expand()
        bar._collapse()
        assert bar._anim.endValue() == QPoint(bar._bar_x, bar._collapsed_y)


# -- _on_send / user_submitted signal -----------------------------------------

class TestSendBehavior:
    def test_empty_input_does_not_emit_signal(self, bar, qtbot):
        bar.input_box.setText("")
        with qtbot.assertNotEmitted(bar.user_submitted):
            bar._on_send()

    def test_whitespace_only_does_not_emit_signal(self, bar, qtbot):
        bar.input_box.setText("   ")
        with qtbot.assertNotEmitted(bar.user_submitted):
            bar._on_send()

    def test_valid_input_emits_user_submitted(self, bar, qtbot):
        bar.input_box.setText("I forgot my password")
        with qtbot.waitSignal(bar.user_submitted, timeout=500) as blocker:
            bar._on_send()
        assert blocker.args == ["I forgot my password"]

    def test_signal_carries_stripped_text(self, bar, qtbot):
        bar.input_box.setText("  trim me  ")
        with qtbot.waitSignal(bar.user_submitted, timeout=500) as blocker:
            bar._on_send()
        assert blocker.args == ["trim me"]

    def test_send_clears_input_box(self, bar, qtbot):
        bar.input_box.setText("some text")
        with qtbot.waitSignal(bar.user_submitted, timeout=500):
            bar._on_send()
        assert bar.input_box.text() == ""

    def test_send_sets_status_to_thinking(self, bar, qtbot):
        bar.input_box.setText("help me")
        with qtbot.waitSignal(bar.user_submitted, timeout=500):
            bar._on_send()
        assert bar.status_label.text() == "Thinking\u2026"

    def test_return_pressed_triggers_send(self, bar, qtbot):
        bar.input_box.setText("press enter")
        with qtbot.waitSignal(bar.user_submitted, timeout=500) as blocker:
            qtbot.keyPress(bar.input_box, Qt.Key.Key_Return)
        assert blocker.args == ["press enter"]


# -- set_status ----------------------------------------------------------------

class TestSetStatus:
    def test_updates_label_text(self, bar):
        bar.set_status("Thinking\u2026")
        assert bar.status_label.text() == "Thinking\u2026"

    def test_ready_restores_placeholder(self, bar):
        bar.set_status("Thinking\u2026")
        bar.set_status("Ready")
        assert "Ask Halo" in bar.input_box.placeholderText()

    def test_non_ready_sets_placeholder(self, bar):
        bar.set_status("Tap the highlighted area")
        assert bar.input_box.placeholderText() == "Tap the highlighted area"
