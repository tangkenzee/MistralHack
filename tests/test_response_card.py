"""
tests/test_response_card.py
============================
Tests for ResponseCard (aliased as ChatPanel) -- cursor-dodging reply card.

Requires pytest-qt (qtbot fixture).
"""

import pytest
from unittest.mock import patch, PropertyMock
from PyQt6.QtCore import Qt, QPoint

from overlay_ui import (
    ResponseCard, ChatPanel, CARD_W, CARD_MIN_H,
    CARD_MARGIN, CARD_DODGE_PAD,
)


@pytest.fixture
def card(qtbot):
    c = ResponseCard()
    qtbot.addWidget(c)
    return c


# -- Backward-compat alias ----------------------------------------------------

class TestAlias:
    def test_chatpanel_is_response_card(self):
        assert ChatPanel is ResponseCard


# -- Construction --------------------------------------------------------------

class TestConstruction:
    def test_fixed_width(self, card):
        assert card.width() == CARD_W

    def test_fixed_height(self, card):
        assert card.height() == CARD_MIN_H

    def test_window_flag_frameless(self, card):
        assert card.windowFlags() & Qt.WindowType.FramelessWindowHint

    def test_window_flag_always_on_top(self, card):
        assert card.windowFlags() & Qt.WindowType.WindowStaysOnTopHint

    def test_history_is_read_only(self, card):
        assert card.history.isReadOnly()

    def test_status_label_starts_ready(self, card):
        assert card.status_label.text() == "Ready"

    def test_starts_on_right(self, card):
        assert card._on_right is True


# -- Dodge positions -----------------------------------------------------------

class TestDodgePositions:
    def test_pos_right_x(self, card):
        from PyQt6.QtWidgets import QApplication
        sw = QApplication.primaryScreen().geometry().width()
        assert card._pos_right.x() == sw - CARD_W - CARD_MARGIN

    def test_pos_left_x(self, card):
        assert card._pos_left.x() == CARD_MARGIN

    def test_initial_position_is_right(self, card):
        assert card.pos() == card._pos_right

    def test_slide_to_left(self, card):
        card._slide_to(card._pos_left)
        assert card._anim.endValue() == card._pos_left

    def test_slide_to_right(self, card):
        card._slide_to(card._pos_right)
        assert card._anim.endValue() == card._pos_right


# -- Cursor dodging logic ------------------------------------------------------

class TestCursorDodge:
    def test_dodge_flips_to_left_when_cursor_near_right(self, card):
        """When cursor is inside padded rect and card is on right, dodge left."""
        card._on_right = True
        card.move(card._pos_right)
        # Simulate cursor at card centre
        centre = card.geometry().center()
        with patch("overlay_ui.QCursor.pos", return_value=centre):
            card._check_cursor()
        assert card._on_right is False
        assert card._anim.endValue() == card._pos_left

    def test_dodge_flips_to_right_when_cursor_near_left(self, card):
        card._on_right = False
        card.move(card._pos_left)
        centre = card.geometry().center()
        with patch("overlay_ui.QCursor.pos", return_value=centre):
            card._check_cursor()
        assert card._on_right is True
        assert card._anim.endValue() == card._pos_right

    def test_no_dodge_when_cursor_far_away(self, card):
        card._on_right = True
        card.move(card._pos_right)
        far = QPoint(0, 0)
        with patch("overlay_ui.QCursor.pos", return_value=far):
            card._check_cursor()
        assert card._on_right is True  # unchanged

    def test_timer_is_running(self, card):
        assert card._dodge_timer.isActive()


# -- append_message ------------------------------------------------------------

class TestAppendMessage:
    def test_message_appears_in_history(self, card):
        card.append_message("You", "hello world")
        assert "hello world" in card.history.toPlainText()

    def test_sender_appears_in_history(self, card):
        card.append_message("Halo", "some text")
        assert "Halo" in card.history.toHtml()

    def test_multiple_messages_accumulate(self, card):
        card.append_message("You", "first message")
        card.append_message("Halo", "second message")
        html = card.history.toPlainText()
        assert "first message" in html
        assert "second message" in html

    def test_default_color_parameter_does_not_raise(self, card):
        card.append_message("You", "test")

    def test_html_entities_in_message_do_not_crash(self, card):
        card.append_message("You", "<b>bold</b> & 'quotes'")


# -- set_status ----------------------------------------------------------------

class TestSetStatus:
    def test_updates_label_text(self, card):
        card.set_status("Thinking\u2026")
        assert card.status_label.text() == "Thinking\u2026"

    def test_empty_string_accepted(self, card):
        card.set_status("")
        assert card.status_label.text() == ""

    def test_multiple_updates(self, card):
        card.set_status("A")
        card.set_status("B")
        assert card.status_label.text() == "B"
