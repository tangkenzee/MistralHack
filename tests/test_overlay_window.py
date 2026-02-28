"""
tests/test_overlay_window.py
============================
Tests for OverlayWindow — the full-screen, transparent, click-through
painting surface.

Requires pytest-qt (qtbot fixture).
"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QApplication

from overlay_ui import (
    OverlayWindow, _exclude_from_capture, WDA_EXCLUDEFROMCAPTURE,
    DIM_SCRIM, CUTOUT_RADIUS, CUTOUT_BORDER, CUTOUT_BORDER_W,
    PULSE_RINGS, PULSE_MAX_SPREAD, PULSE_DURATION, PULSE_COLOR,
)


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

    def test_pulse_phase_starts_at_zero(self, overlay):
        assert overlay._pulse == 0.0

    def test_pulse_anim_not_running_on_init(self, overlay):
        from PyQt6.QtCore import QPropertyAnimation
        assert overlay._pulse_anim.state() != QPropertyAnimation.State.Running

    def test_window_flag_frameless(self, overlay):
        flags = overlay.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint

    def test_window_flag_always_on_top(self, overlay):
        flags = overlay.windowFlags()
        assert flags & Qt.WindowType.WindowStaysOnTopHint

    def test_window_flag_tool(self, overlay):
        flags = overlay.windowFlags()
        assert flags & Qt.WindowType.Tool

    def test_window_flag_transparent_for_input(self, overlay):
        flags = overlay.windowFlags()
        assert flags & Qt.WindowType.WindowTransparentForInput

    def test_attribute_translucent_background(self, overlay):
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def test_attribute_transparent_for_mouse_events(self, overlay):
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def test_geometry_matches_primary_screen(self, overlay):
        screen_geo = QApplication.primaryScreen().geometry()
        assert overlay.geometry() == screen_geo


# ── Dim-scrim constants ──────────────────────────────────────────────────────

class TestDimScrimConstants:
    def test_dim_scrim_is_semitransparent_black(self):
        assert DIM_SCRIM.red() == 0
        assert DIM_SCRIM.green() == 0
        assert DIM_SCRIM.blue() == 0
        assert 0 < DIM_SCRIM.alpha() < 255

    def test_cutout_radius_positive(self):
        assert CUTOUT_RADIUS > 0

    def test_cutout_border_has_alpha(self):
        assert 0 < CUTOUT_BORDER.alpha() < 255

    def test_cutout_border_width_positive(self):
        assert CUTOUT_BORDER_W > 0


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

    def test_pulse_starts_on_highlight(self, overlay):
        overlay.show_highlight(10, 10, 100, 50)
        from PyQt6.QtCore import QPropertyAnimation
        assert overlay._pulse_anim.state() == QPropertyAnimation.State.Running


# ── clear_highlight ─────────────────────────────────────────────────────────

class TestClearHighlight:
    def test_clears_after_show(self, overlay):
        overlay.show_highlight(100, 200, 150, 30)
        overlay.clear_highlight()
        assert overlay._highlight is None

    def test_pulse_stops_on_clear(self, overlay):
        overlay.show_highlight(10, 10, 100, 50)
        overlay.clear_highlight()
        from PyQt6.QtCore import QPropertyAnimation
        assert overlay._pulse_anim.state() != QPropertyAnimation.State.Running
        assert overlay._pulse == 0.0

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


# ── Capture exclusion ─────────────────────────────────────────────────────────

class TestCaptureExclusion:
    def test_constant_value(self):
        assert WDA_EXCLUDEFROMCAPTURE == 0x00000011

    def test_exclude_calls_set_window_display_affinity(self, overlay):
        """_exclude_from_capture should call SetWindowDisplayAffinity with
        the widget's HWND and WDA_EXCLUDEFROMCAPTURE."""
        mock_set = MagicMock()
        with patch("overlay_ui.ctypes") as mock_ctypes, \
             patch("overlay_ui.sys") as mock_sys:
            mock_sys.platform = "win32"
            mock_ctypes.windll.user32.SetWindowDisplayAffinity = mock_set
            _exclude_from_capture(overlay)
            mock_set.assert_called_once_with(
                int(overlay.winId()), WDA_EXCLUDEFROMCAPTURE
            )

    def test_exclude_noop_on_non_windows(self, overlay):
        """On non-Windows platforms _exclude_from_capture should do nothing."""
        mock_set = MagicMock()
        with patch("overlay_ui.ctypes") as mock_ctypes, \
             patch("overlay_ui.sys") as mock_sys:
            mock_sys.platform = "linux"
            mock_ctypes.windll.user32.SetWindowDisplayAffinity = mock_set
            _exclude_from_capture(overlay)
            mock_set.assert_not_called()

    def test_exclude_swallows_exceptions(self, overlay):
        """Should not crash even if the Win32 call fails."""
        with patch("overlay_ui.ctypes") as mock_ctypes, \
             patch("overlay_ui.sys") as mock_sys:
            mock_sys.platform = "win32"
            mock_ctypes.windll.user32.SetWindowDisplayAffinity.side_effect = OSError
            _exclude_from_capture(overlay)  # must not raise
