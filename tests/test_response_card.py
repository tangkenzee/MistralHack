"""
tests/test_response_card.py
============================
Tests for ResponseCard (aliased as ChatPanel) -- 2D cursor-dodging reply card.

Requires pytest-qt (qtbot fixture).
"""

import pytest
from unittest.mock import patch
from PyQt6.QtCore import Qt, QPoint

from overlay_ui import (
    ResponseCard, ChatPanel, CARD_W, CARD_MIN_H,
    CARD_MARGIN, CARD_DODGE_PAD, CARD_DODGE_DIST, CARD_STUCK_THRESH,
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

    def test_screen_rect_stored(self, card):
        assert card._screen is not None

    def test_timer_is_running(self, card):
        assert card._dodge_timer.isActive()


# -- 2D Cursor dodging --------------------------------------------------------

class TestCursorDodge:
    def test_no_dodge_when_cursor_far_away(self, card):
        """Card should not move when cursor is far from it."""
        original = card.pos()
        far = QPoint(0, 0)
        with patch("overlay_ui.QCursor.pos", return_value=far):
            card._check_cursor()
        assert card.pos() == original

    def test_dodge_away_from_cursor_on_left(self, card):
        """When cursor approaches from the left, card should move rightward."""
        # Centre the card so it has room to dodge right
        card.move(card._screen.width() // 2, card._screen.height() // 2)
        geo = card.geometry()
        left_edge = QPoint(geo.left() - CARD_DODGE_PAD + 5, geo.center().y())
        with patch("overlay_ui.QCursor.pos", return_value=left_edge):
            card._check_cursor()
        assert card._anim.endValue().x() > geo.x()

    def test_dodge_away_from_cursor_on_right(self, card):
        """When cursor approaches from the right, card should move leftward."""
        # Place card in centre so it has room to dodge left
        card.move(card._screen.width() // 2, card._screen.height() // 2)
        geo = card.geometry()
        right_edge = QPoint(geo.right() + CARD_DODGE_PAD - 5, geo.center().y())
        with patch("overlay_ui.QCursor.pos", return_value=right_edge):
            card._check_cursor()
        assert card._anim.endValue().x() < geo.x()

    def test_dodge_away_from_cursor_above(self, card):
        """When cursor approaches from above, card should move downward."""
        card.move(card._screen.width() // 2, card._screen.height() // 2)
        geo = card.geometry()
        above = QPoint(geo.center().x(), geo.top() - CARD_DODGE_PAD + 5)
        with patch("overlay_ui.QCursor.pos", return_value=above):
            card._check_cursor()
        assert card._anim.endValue().y() > geo.y()

    def test_dodge_away_from_cursor_below(self, card):
        """When cursor approaches from below, card should move upward."""
        card.move(card._screen.width() // 2, CARD_MIN_H + CARD_MARGIN + 50)
        geo = card.geometry()
        below = QPoint(geo.center().x(), geo.bottom() + CARD_DODGE_PAD - 5)
        with patch("overlay_ui.QCursor.pos", return_value=below):
            card._check_cursor()
        assert card._anim.endValue().y() < geo.y()

    def test_dodge_clamped_to_left_margin(self, card):
        """Card should never go past the left margin."""
        card.move(CARD_MARGIN, card._screen.height() // 2)
        geo = card.geometry()
        right_of_card = QPoint(geo.right() + CARD_DODGE_PAD - 5, geo.center().y())
        with patch("overlay_ui.QCursor.pos", return_value=right_of_card):
            card._check_cursor()
        assert card._anim.endValue().x() >= CARD_MARGIN

    def test_dodge_clamped_to_top_margin(self, card):
        """Card should never go past the top margin."""
        card.move(card._screen.width() // 2, CARD_MARGIN)
        geo = card.geometry()
        below_card = QPoint(geo.center().x(), geo.bottom() + CARD_DODGE_PAD - 5)
        with patch("overlay_ui.QCursor.pos", return_value=below_card):
            card._check_cursor()
        assert card._anim.endValue().y() >= CARD_MARGIN

    def test_corner_stuck_deflects(self, card):
        """Card pinned in top-left corner should deflect away instead of
        staying stuck."""
        card.move(CARD_MARGIN, CARD_MARGIN)  # pin in top-left
        geo = card.geometry()
        # cursor approaches from bottom-right → naive push goes further into corner
        cursor = QPoint(geo.right() + CARD_DODGE_PAD - 5,
                        geo.bottom() + CARD_DODGE_PAD - 5)
        with patch("overlay_ui.QCursor.pos", return_value=cursor):
            card._check_cursor()
        # Should have found an escape direction (not stayed at CARD_MARGIN, CARD_MARGIN)
        end = card._anim.endValue()
        moved = ((end.x() - CARD_MARGIN) ** 2 + (end.y() - CARD_MARGIN) ** 2) ** 0.5
        assert moved >= CARD_STUCK_THRESH

    def test_bottom_right_corner_deflects(self, card):
        """Card pinned in bottom-right corner should escape."""
        max_x = card._screen.width()  - CARD_W      - CARD_MARGIN
        max_y = card._screen.height() - CARD_MIN_H  - CARD_MARGIN
        card.move(max_x, max_y)
        geo = card.geometry()
        # cursor from top-left → naive push goes further into corner
        cursor = QPoint(geo.left() - CARD_DODGE_PAD + 5,
                        geo.top()  - CARD_DODGE_PAD + 5)
        with patch("overlay_ui.QCursor.pos", return_value=cursor):
            card._check_cursor()
        end = card._anim.endValue()
        moved = ((end.x() - max_x) ** 2 + (end.y() - max_y) ** 2) ** 0.5
        assert moved >= CARD_STUCK_THRESH

    def test_dodge_target_returns_none_when_stuck(self, card):
        """_dodge_target should return None when the movement is < threshold."""
        card.move(CARD_MARGIN, CARD_MARGIN)
        # direction pointing into the top-left corner
        result = card._dodge_target(-1.0, -1.0,
                                    card.geometry().center().x(),
                                    card.geometry().center().y())
        assert result is None

    def test_no_interrupt_during_animation(self, card):
        """Should not start a new dodge while an animation is running."""
        card._slide_to(QPoint(100, 100))  # start animation
        geo = card.geometry()
        cursor = QPoint(geo.center().x(), geo.center().y())
        with patch("overlay_ui.QCursor.pos", return_value=cursor):
            card._check_cursor()  # should be a no-op
        # The animation target should still be (100, 100)
        assert card._anim.endValue() == QPoint(100, 100)


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
