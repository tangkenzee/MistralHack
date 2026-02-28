"""
tests/test_overlay_window.py
============================
Tests for OverlayWindow — the full-screen, transparent, click-through
painting surface.

Requires pytest-qt (qtbot fixture).
"""

import pytest
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QApplication

from overlay_ui import OverlayWindow


@pytest.fixture
def overlay(qtbot):
    """Create an OverlayWindow, register it with qtbot for cleanup."""
    w = OverlayWindow()
    qtbot.addWidget(w)
    return w


# ── Construction ──────────────────────────────────────────────────────────────

class TestConstruction:
    def test_highlight_is_none_on_init(self, overlay):
        assert overlay._highlight is None

    def test_window_flag_frameless(self, overlay):
        flags = overlay.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint

    def test_window_flag_always_on_top(self, overlay):
        flags = overlay.windowFlags()
        assert flags & Qt.WindowType.WindowStaysOnTopHint

    def test_window_flag_tool(self, overlay):
        flags = overlay.windowFlags()
        assert flags & Qt.WindowType.Tool

    def test_attribute_translucent_background(self, overlay):
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def test_attribute_transparent_for_mouse_events(self, overlay):
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def test_geometry_matches_primary_screen(self, overlay):
        screen_geo = QApplication.primaryScreen().geometry()
        assert overlay.geometry() == screen_geo


# ── show_highlight ────────────────────────────────────────────────────────────

class TestShowHighlight:
    def test_sets_highlight_rect(self, overlay):
        overlay.show_highlight(100, 200, 150, 30)
        assert overlay._highlight == QRect(100, 200, 150, 30)

    def test_overwrites_previous_highlight(self, overlay):
        overlay.show_highlight(10, 20, 30, 40)
        overlay.show_highlight(50, 60, 70, 80)
        assert overlay._highlight == QRect(50, 60, 70, 80)

    def test_highlight_stores_exact_values(self, overlay):
        overlay.show_highlight(0, 0, 1, 1)
        r = overlay._highlight
        assert r.x() == 0
        assert r.y() == 0
        assert r.width() == 1
        assert r.height() == 1

    def test_large_coordinates_accepted(self, overlay):
        overlay.show_highlight(3840, 2160, 800, 200)
        assert overlay._highlight == QRect(3840, 2160, 800, 200)


# ── clear_highlight ───────────────────────────────────────────────────────────

class TestClearHighlight:
    def test_clears_after_show(self, overlay):
        overlay.show_highlight(100, 200, 150, 30)
        overlay.clear_highlight()
        assert overlay._highlight is None

    def test_clear_when_already_none_is_safe(self, overlay):
        """Calling clear with no active highlight must not raise."""
        overlay.clear_highlight()
        assert overlay._highlight is None

    def test_show_then_clear_then_show_cycle(self, overlay):
        overlay.show_highlight(1, 2, 3, 4)
        overlay.clear_highlight()
        overlay.show_highlight(5, 6, 7, 8)
        assert overlay._highlight == QRect(5, 6, 7, 8)


# ── paintEvent safety ─────────────────────────────────────────────────────────

class TestPaintEvent:
    def test_repaint_with_no_highlight_does_not_raise(self, overlay, qtbot):
        """paintEvent must be a no-op (not crash) when _highlight is None."""
        overlay.show()
        overlay.repaint()   # exercises paintEvent with _highlight=None

    def test_repaint_with_highlight_does_not_raise(self, overlay, qtbot):
        """paintEvent must not crash when there is a valid highlight rect."""
        overlay.show_highlight(200, 300, 120, 40)
        overlay.show()
        overlay.repaint()

    def test_repaint_after_clear_does_not_raise(self, overlay, qtbot):
        overlay.show_highlight(200, 300, 120, 40)
        overlay.clear_highlight()
        overlay.show()
        overlay.repaint()
