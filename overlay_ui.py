"""
Halo - overlay_ui.py
====================
The "Glass" layer: a transparent, frameless, always-on-top PyQt6 overlay
with a spotlight input bar and cursor-dodging response card.
Delegates all AI/vision work to the ai_brain package via AIWorker (QThread)
so the UI never blocks.

Architecture:
  OverlayWindow  – full-screen, click-through, paints dim scrim + clear cutout.
  SpotlightBar   – iPhone-notch-style input bar fused to top-centre of screen.
  ResponseCard   – always-visible reply card that dodges the cursor.
  AIWorker       – background thread; wraps ai_brain one-shot or Session step.
  _HotkeyBridge  – QObject that relays keyboard hotkeys to the Qt main thread.
  HaloApp        – top-level wiring that owns all windows + the active Session.

Global hotkeys (work even when the overlay has no keyboard focus):
  Alt+N  – take a screenshot and advance the AI session (repeat after each action)
  Alt+R  – reset the session and clear the highlight
"""

import sys
import math
import signal
import os
import ctypes
import random
import asyncio
from pathlib import Path
import mss
try:
    import keyboard
except ImportError:
    keyboard = None  # hotkeys disabled when package unavailable (e.g. CI)
from PyQt6.QtCore import (
    Qt, QThread, QObject, pyqtSignal, QRect, QPoint, QRectF,
    QPropertyAnimation, QEasingCurve, QEvent, pyqtProperty, QTimer,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QFont, QScreen, QIcon,
    QBrush, QPainterPath, QPalette, QCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel,
    QGraphicsDropShadowEffect,
)

import ai_brain
from ai_brain import Session
from ai_brain.speech_to_text import realtime_transcribe
from ai_brain.text_to_speech import speak, stop_speaking

# ─── Paths ────────────────────────────────────────────────────────────────────
_ROOT      = Path(__file__).parent
_ICON_PATH = _ROOT / "icons" / "halo_logo.svg"


# ─── Constants ────────────────────────────────────────────────────────────────
# ── Dim-overlay (spotlight cutout) ──
DIM_SCRIM         = QColor(0, 0, 0, 180)        # dark backdrop when highlighting
CUTOUT_RADIUS     = 12                          # corner radius of the clear cutout
CUTOUT_BORDER     = QColor(255, 255, 255, 55)   # matches SPOT_GLASS_BORDER
CUTOUT_BORDER_W   = 1.5                         # border stroke width
PULSE_RINGS       = 3                           # number of outward-ripple rings
PULSE_MAX_SPREAD  = 72                          # max px each ring expands outward
PULSE_DURATION    = 2000                        # full cycle in ms
PULSE_COLOR       = QColor(255, 255, 255)       # base colour for pulse rings

# ── Spotlight-specific glass ──
SPOTLIGHT_H       = 44     # spotlight bar height (slimmer, like Spotlight)
NOTCH_PEEK        = 10     # pixels visible when the notch is collapsed
NOTCH_BOUNCE_PX   = 12     # how far the notch pops down during bounce
NOTCH_BOUNCE_MS   = 800    # bounce animation duration (ms)
NOTCH_BOUNCE_INT  = 5000   # interval between bounces (ms)

# ── Spotlight-specific glass ──
SPOT_GLASS_BASE   = QColor(40, 40, 42, 155)      # lighter, more see-through
SPOT_GLASS_BORDER = QColor(255, 255, 255, 55)     # clearly visible thin rim
SPOTLIGHT_W       = 534    # spotlight bar width  (matches macOS Spotlight)
CARD_W            = 340    # response card width
CARD_MIN_H        = 320    # response card height (taller for message history)
CARD_MARGIN       = 16     # gap between card edge and screen edge
CARD_DODGE_PAD    = 60     # proximity threshold to start dodging cursor
CARD_DODGE_DIST   = 400    # how far the card flies when dodging
CARD_STUCK_THRESH = 20     # min px movement; below this we try deflecting
# Modern Apple-like sans-serif; Qt falls back gracefully if unavailable
FONT_FAMILY       = "Segoe UI Variable"

# ── Typewriter effect ──
TYPE_MIN_DELAY    = 15     # fastest tick (ms)
TYPE_MAX_DELAY    = 55     # slowest tick (ms)
TYPE_MIN_CHARS    = 1      # min chars revealed per tick
TYPE_MAX_CHARS    = 3      # max chars revealed per tick

SCREENSHOT_PATH   = "images/raw.png"

# Windows 10 2004+ flag: window is visible on screen but excluded from
# all capture APIs (mss, PrintScreen, OBS, etc.).
WDA_EXCLUDEFROMCAPTURE = 0x00000011

# When True (default), the overlay is hidden from screenshots / screen-capture.
# Set HIDE_OVERLAY=false in .env to include the overlay in captures.
_HIDE_OVERLAY = os.getenv("HIDE_OVERLAY", "true").strip().lower() in ("true", "1", "yes")

def _exclude_from_capture(widget):
    """Mark *widget* invisible to screenshot / screen-capture tools.
    Uses SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE).  Requires the
    native HWND, so we call winId() first (creates it if needed).
    Controlled by HIDE_OVERLAY env flag (default: true).
    Silently ignored on non-Windows or older builds."""
    if not _HIDE_OVERLAY:
        return
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    except Exception:
        pass   # gracefully degrade on older Windows


# ─── Worker Thread ────────────────────────────────────────────────────────────
class AIWorker(QThread):
    """
    Runs ai_brain logic in a background thread so the UI never blocks.

    Two modes:
      • session mode  – pass a Session object; calls session.next_step() so
                        conversation history is preserved across steps.
      • one-shot mode – no session; calls ai_brain.get_target_coordinates()
                        (used by unit tests and legacy code paths).

    Emits `result_ready` with the SSOT-guaranteed dict when done,
    or `error` with a message string on failure.
    """
    result_ready = pyqtSignal(dict)
    error        = pyqtSignal(str)

    def __init__(self, screenshot_path: str, user_prompt: str | None = None,
                 session: Session | None = None):
        super().__init__()
        self.screenshot_path = screenshot_path
        self.user_prompt     = user_prompt
        self.session         = session

    def run(self):
        try:
            if self.session is not None:
                result = self.session.next_step(self.screenshot_path, self.user_prompt)
            else:
                result = ai_brain.get_target_coordinates(
                    self.screenshot_path,
                    self.user_prompt,
                )
            self.result_ready.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ─── STT Worker Thread ───────────────────────────────────────────────────────
class RealtimeSTTWorker(QThread):
    """
    Runs the Voxtral realtime transcription in a background thread.
    Streams microphone audio → Voxtral and emits text deltas as they
    arrive so the overlay can display live captions.

    Signals:
        text_delta(str)  – incremental text fragment from the model
        done()           – transcription stream finished cleanly
        error(str)       – something went wrong
    """
    text_delta = pyqtSignal(str)
    done       = pyqtSignal()
    error      = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._stop_event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(self):
        """Entry point for the QThread — spins up an asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()

        self._loop.run_until_complete(
            realtime_transcribe(
                stop_event=self._stop_event,
                on_delta=self._emit_delta,
                on_done=self._emit_done,
                on_error=self._emit_error,
            )
        )
        self._loop.close()

    # ── Thread-safe signal wrappers (called from the asyncio loop) ──
    def _emit_delta(self, text: str):
        self.text_delta.emit(text)

    def _emit_done(self):
        self.done.emit()

    def _emit_error(self, msg: str):
        self.error.emit(msg)

    def request_stop(self):
        """Ask the microphone iterator to finish (called from the main thread)."""
        if self._stop_event is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)


# ─── TTS Worker Thread ──────────────────────────────────────────────────────
class TTSWorker(QThread):
    """
    Runs ElevenLabs text-to-speech in a background thread.
    Streams audio playback so the UI stays responsive.

    Signals:
        started_speaking()  – playback has begun
        finished_speaking() – playback completed or was interrupted
        error(str)          – something went wrong
    """
    started_speaking  = pyqtSignal()
    finished_speaking = pyqtSignal()
    error             = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        speak(
            self._text,
            on_start=lambda: self.started_speaking.emit(),
            on_done=lambda: self.finished_speaking.emit(),
            on_error=lambda msg: self.error.emit(msg),
        )

    def request_stop(self):
        """Interrupt playback as soon as possible."""
        stop_speaking()


# ─── Full-Screen Overlay (paint-only, click-through) ─────────────────────────
class OverlayWindow(QWidget):
    """
    A transparent, frameless, always-on-top window that covers the full
    screen. It is completely click-through so underlying apps still work.
    Paints a dimmed backdrop with a clear cutout + pulsing border rings.
    """

    # ── Pulse property (0.0 → 1.0 looping) ──────────────────────────────
    def _get_pulse(self) -> float:
        return self._pulse

    def _set_pulse(self, val: float):
        self._pulse = val
        if self._highlight:
            self.update()

    pulse_phase = pyqtProperty(float, _get_pulse, _set_pulse)

    def __init__(self):
        super().__init__()
        self._highlight: QRect | None = None
        self._pulse = 0.0
        self._exclude_widgets: list[QWidget] = []  # widgets exempt from dim

        self._pulse_anim = QPropertyAnimation(self, b"pulse_phase", self)
        self._pulse_anim.setDuration(PULSE_DURATION)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setLoopCount(-1)          # loop forever

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # WA_ flag for child-widget passthrough (belt-and-suspenders)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        screen: QScreen = QApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        self.setStyleSheet("background: transparent;")
        _exclude_from_capture(self)

    # ── Public API ──────────────────────────────────────────────────────────
    def show_highlight(self, x: int, y: int, width: int, height: int):
        # OpenCV coordinates are in physical (mss) pixels; scale to Qt logical
        dpr = QApplication.primaryScreen().devicePixelRatio()
        lx = int(x / dpr)
        ly = int(y / dpr)
        lw = int(width / dpr)
        lh = int(height / dpr)
        print(f"[OVERLAY] show_highlight  raw=({x},{y},{width},{height})  "
              f"dpr={dpr}  logical=({lx},{ly},{lw},{lh})  "
              f"overlay_geom={self.geometry()}  visible={self.isVisible()}")
        self._highlight = QRect(lx, ly, lw, lh)
        self._pulse_anim.start()
        self.raise_()
        self.repaint()

    def clear_highlight(self):
        self._highlight = None
        self._pulse_anim.stop()
        self._pulse = 0.0
        self.update()

    # ── Paint ───────────────────────────────────────────────────────────────
    def paintEvent(self, _event):
        if not self._highlight:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self._highlight
        r = float(CUTOUT_RADIUS)

        # 1) Build a path covering the whole screen …
        full = QPainterPath()
        full.addRect(QRectF(self.rect()))

        # 2) … subtract the highlight rect (rounded) to create a cutout
        cutout = QPainterPath()
        cutout.addRoundedRect(QRectF(rect), r, r)
        dimmed = full - cutout

        # 2b) Also subtract any registered UI widgets (bar, card) so they
        #     appear above the dim scrim without being darkened.
        for w in self._exclude_widgets:
            if w.isVisible():
                wcut = QPainterPath()
                wcut.addRoundedRect(QRectF(w.geometry()), r, r)
                dimmed = dimmed - wcut

        # 3) Fill the dimmed region
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(DIM_SCRIM))
        painter.drawPath(dimmed)

        # 4) Draw a thin glass-style border around the cutout
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(CUTOUT_BORDER, CUTOUT_BORDER_W))
        painter.drawRoundedRect(QRectF(rect), r, r)

        # 5) Pulsing rings radiating outward from the border
        phase = self._pulse
        for i in range(PULSE_RINGS):
            # Stagger each ring evenly across the cycle
            ring_phase = (phase + i / PULSE_RINGS) % 1.0
            spread = ring_phase * PULSE_MAX_SPREAD
            # Fade out as the ring expands (peaks at ~0.15, fades to 0)
            alpha = int(160 * (1.0 - ring_phase) ** 1.5)
            if alpha < 1:
                continue
            c = QColor(PULSE_COLOR)
            c.setAlpha(alpha)
            painter.setPen(QPen(c, 1.5))
            painter.drawRoundedRect(
                QRectF(rect).adjusted(-spread, -spread, spread, spread),
                r + spread * 0.3, r + spread * 0.3,
            )

        painter.end()

# ─── Animated Glass Button ─────────────────────────────────────────────────
class GlassButton(QPushButton):
    """
    Pill button with a smooth frosted-glass hover animation.
    Starts as a barely-visible rim; brightens on hover; dims on press.
    No solid colour — purely achromatic glass.
    """

    def _get_hover(self) -> float:
        return self._hover

    def _set_hover(self, val: float):
        self._hover = val
        self.update()

    hover_progress = pyqtProperty(float, _get_hover, _set_hover)

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._hover = 0.0
        self._anim = QPropertyAnimation(self, b"hover_progress", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("background: transparent; border: none;")

    def event(self, e):
        t = e.type()
        if t == QEvent.Type.HoverEnter:
            self._anim.stop()
            self._anim.setStartValue(self._hover)
            self._anim.setEndValue(1.0)
            self._anim.start()
        elif t == QEvent.Type.HoverLeave:
            self._anim.stop()
            self._anim.setStartValue(self._hover)
            self._anim.setEndValue(0.0)
            self._anim.start()
        return super().event(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2.0
        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        t = self._hover
        scale = 0.72 if self.isDown() else 1.0
        enabled = self.isEnabled()
        opacity = 0.35 if not enabled else 1.0

        # Frosted fill: faint at rest → brighter on hover
        fill_a = int((12 + t * 38) * scale * opacity)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(255, 255, 255, fill_a)))
        p.drawRoundedRect(rect, r, r)

        # Outer glow — wide soft ring that blooms on hover
        glow_a = int(t * 38 * scale * opacity)
        if glow_a > 0:
            glow_pen = QPen(QColor(255, 255, 255, glow_a), 4.0)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(glow_pen)
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)

        # Rim: clearly visible at rest → full white on hover
        rim_a = int((75 + t * 145) * scale * opacity)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, rim_a), 1.2))
        p.drawRoundedRect(rect, r, r)

        # Icon glyph
        icon_a = int((140 + t * 115) * scale * opacity)
        pen = QPen(QColor(255, 255, 255, icon_a))
        pen.setWidthF(1.0)
        p.setPen(pen)
        p.setFont(self.font())
        p.drawText(rect.toRect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


# ─── Notch Input Bar ──────────────────────────────────────────────────────────
class MicButton(QPushButton):
    """
    A small circular microphone toggle button that glows red when recording.
    Uses Segoe MDL2 Assets glyph \uE720 (Microphone).
    """

    def _get_hover(self) -> float:
        return self._hover

    def _set_hover(self, val: float):
        self._hover = val
        self.update()

    hover_progress = pyqtProperty(float, _get_hover, _set_hover)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover = 0.0
        self._recording = False
        self._anim = QPropertyAnimation(self, b"hover_progress", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setFixedSize(30, 30)
        self.setStyleSheet("background: transparent; border: none;")

    def set_recording(self, recording: bool):
        self._recording = recording
        self.update()

    def event(self, e):
        t = e.type()
        if t == QEvent.Type.HoverEnter:
            self._anim.stop()
            self._anim.setStartValue(self._hover)
            self._anim.setEndValue(1.0)
            self._anim.start()
        elif t == QEvent.Type.HoverLeave:
            self._anim.stop()
            self._anim.setStartValue(self._hover)
            self._anim.setEndValue(0.0)
            self._anim.start()
        return super().event(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = min(w, h) / 2.0
        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        t = self._hover
        scale = 0.85 if self.isDown() else 1.0

        if self._recording:
            # Glowing red circle when recording
            fill_a = int((80 + t * 60) * scale)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 60, 50, fill_a)))
            p.drawEllipse(rect)

            # Red rim
            rim_a = int((180 + t * 75) * scale)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 60, 50, rim_a), 1.4))
            p.drawEllipse(rect)

            # White mic icon
            icon_a = int(255 * scale)
            p.setPen(QPen(QColor(255, 255, 255, icon_a)))
        else:
            # Subtle frosted circle at rest
            fill_a = int((8 + t * 30) * scale)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 255, 255, fill_a)))
            p.drawEllipse(rect)

            # Rim
            rim_a = int((60 + t * 140) * scale)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, rim_a), 1.0))
            p.drawEllipse(rect)

            # Muted mic icon
            icon_a = int((120 + t * 100) * scale)
            p.setPen(QPen(QColor(255, 255, 255, icon_a)))

        # Draw mic glyph (Segoe MDL2 Assets: \uE720)
        p.setFont(QFont("Segoe MDL2 Assets", 12))
        p.drawText(rect.toRect(), Qt.AlignmentFlag.AlignCenter, "\uE720")
        p.end()


class SpotlightBar(QWidget):
    """
    iPhone-notch-style input bar fused to the top-centre of the screen.
    In its default (collapsed) state only a small tab peeks down from
    the top edge.  Hovering over the tab slides the full bar into view;
    moving the mouse away (and removing input focus) collapses it again.
    Emits user_submitted(prompt) on send.
    """
    user_submitted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._expanded = False
        self.status_label = QLabel("Ready")
        self._stt_worker: RealtimeSTTWorker | None = None
        self._live_text = ""             # accumulated realtime transcription
        self._build_ui()
        self._setup_notch()

    # ── UI construction ──────────────────────────────────────────────────
    def _build_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(SPOTLIGHT_W, SPOTLIGHT_H)
        _exclude_from_capture(self)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # Magnifying-glass icon (Segoe MDL2 Assets ships with Windows 10/11)
        search_icon = QLabel("\uE721")
        search_icon.setFont(QFont("Segoe MDL2 Assets", 14))
        search_icon.setStyleSheet("color: rgba(255, 255, 255, 110);")
        search_icon.setFixedSize(22, 22)
        search_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Ask Halo\u2026")
        self.input_box.setFont(QFont(FONT_FAMILY, 15))
        self.input_box.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: rgba(255, 255, 255, 230);
                border: none;
                padding: 0px;
            }
        """)
        # Muted placeholder text colour (matches Spotlight ~47% white)
        pal = self.input_box.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(255, 255, 255, 120))
        self.input_box.setPalette(pal)
        self.input_box.returnPressed.connect(self._on_send)
        self.input_box.installEventFilter(self)   # track focus-out

        # Microphone toggle button
        self.mic_btn = MicButton(self)
        self.mic_btn.setToolTip("Hold to speak")
        self.mic_btn.clicked.connect(self._on_mic_toggle)

        layout.addWidget(search_icon)
        layout.addWidget(self.input_box, stretch=1)
        layout.addWidget(self.mic_btn)

    # ── Notch positioning & animation ────────────────────────────────────
    def _setup_notch(self):
        """Compute collapsed / expanded Y values and create the slide animation."""
        screen = QApplication.primaryScreen().geometry()
        self._bar_x = (screen.width() - SPOTLIGHT_W) // 2
        self._expanded_y = 0
        self._collapsed_y = -(SPOTLIGHT_H - NOTCH_PEEK)
        self.move(self._bar_x, self._collapsed_y)

        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Bounce animation — keyframed multi-bounce (drop → bounce → smaller → settle)
        self._bounce_anim = QPropertyAnimation(self, b"pos")
        self._bounce_anim.setDuration(NOTCH_BOUNCE_MS)
        self._bounce_anim.setEasingCurve(QEasingCurve.Type.Linear)  # keyframes drive motion
        self._bounce_anim.finished.connect(self._on_bounce_done)

        # Periodic timer to trigger bounce while collapsed
        self._bounce_timer = QTimer(self)
        self._bounce_timer.setInterval(NOTCH_BOUNCE_INT)
        self._bounce_timer.timeout.connect(self._do_bounce)
        self._bounce_timer.start()

    def _expand(self):
        if self._expanded:
            return
        self._expanded = True
        self._bounce_anim.stop()
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(self._bar_x, self._expanded_y))
        self._anim.start()

    def _collapse(self):
        if not self._expanded:
            return
        self._expanded = False
        self._bounce_anim.stop()
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(self._bar_x, self._collapsed_y))
        self._anim.start()

    # ── Periodic bounce ──────────────────────────────────────────────────
    def _do_bounce(self):
        """Pop the notch down with realistic multi-bounce inertia."""
        if self._expanded:
            return
        if self._anim.state() == QPropertyAnimation.State.Running:
            return

        rest = QPoint(self._bar_x, self._collapsed_y)
        bx = self._bar_x
        cy = self._collapsed_y
        pk = NOTCH_BOUNCE_PX

        self._bounce_anim.stop()
        self._bounce_anim.setStartValue(rest)
        self._bounce_anim.setEndValue(rest)

        # Keyframes: drop → return → smaller drop → return → tiny drop → settle
        self._bounce_anim.setKeyValueAt(0.00, QPoint(bx, cy))
        self._bounce_anim.setKeyValueAt(0.15, QPoint(bx, cy + pk))        # main drop
        self._bounce_anim.setKeyValueAt(0.35, QPoint(bx, cy))             # bounce back
        self._bounce_anim.setKeyValueAt(0.50, QPoint(bx, cy + int(pk * 0.45)))  # 2nd drop
        self._bounce_anim.setKeyValueAt(0.65, QPoint(bx, cy))             # bounce back
        self._bounce_anim.setKeyValueAt(0.78, QPoint(bx, cy + int(pk * 0.18)))  # 3rd tiny drop
        self._bounce_anim.setKeyValueAt(0.88, QPoint(bx, cy))             # settle
        self._bounce_anim.setKeyValueAt(1.00, QPoint(bx, cy))             # rest
        self._bounce_anim.start()

    def _on_bounce_done(self):
        """Ensure bar snaps back to collapsed position after bounce."""
        if not self._expanded:
            self.move(self._bar_x, self._collapsed_y)

    # ── Hover / focus events ─────────────────────────────────────────────
    def enterEvent(self, event):
        super().enterEvent(event)
        self._expand()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if not self.input_box.hasFocus():
            self._collapse()

    def eventFilter(self, obj, event):
        """Collapse when the input loses focus and the mouse is outside."""
        if obj is self.input_box and event.type() == QEvent.Type.FocusOut:
            if not self.underMouse():
                self._collapse()
        return super().eventFilter(obj, event)

    # ── Paint: notch shape (flat top, rounded bottom corners) ────────────
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        r = h / 2.0          # full pill radius for bottom corners

        # Notch shape: flat top, rounded bottom
        path = QPainterPath()
        path.moveTo(0, 0)
        path.lineTo(w, 0)
        path.lineTo(w, h - r)
        path.quadTo(w, h, w - r, h)
        path.lineTo(r, h)
        path.quadTo(0, h, 0, h - r)
        path.closeSubpath()

        # Translucent fill (higher transparency than the card)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(SPOT_GLASS_BASE))
        painter.drawPath(path)

        # Visible thin border (Spotlight-style)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(SPOT_GLASS_BORDER, 1.0))
        painter.drawPath(path)
        painter.end()

    # ── Microphone toggle ──────────────────────────────────────────────────
    def _on_mic_toggle(self):
        """Toggle between recording and idle states."""
        if self._stt_worker is not None and self._stt_worker.isRunning():
            # ── Stop recording → finalise ──
            self.mic_btn.set_recording(False)
            self._stt_worker.request_stop()
            # The `done` signal will fire _on_stt_done which auto-submits.
        else:
            # ── Start recording ──
            self._expand()
            self.input_box.clear()
            self._live_text = ""
            self.input_box.setPlaceholderText("Listening\u2026")
            self.mic_btn.set_recording(True)

            self._stt_worker = RealtimeSTTWorker()
            self._stt_worker.text_delta.connect(self._on_stt_delta)
            self._stt_worker.done.connect(self._on_stt_done)
            self._stt_worker.error.connect(self._on_stt_error)
            self._stt_worker.start()

    def _on_stt_delta(self, text: str):
        """Called for each incremental text fragment from Voxtral Realtime."""
        self._live_text += text
        self.input_box.setText(self._live_text)

    def _on_stt_done(self):
        """Called when the realtime transcription stream finishes."""
        self.mic_btn.set_recording(False)
        final = self._live_text.strip()
        if final:
            self.input_box.setText(final)
            self._on_send()                    # auto-submit the transcribed text
        else:
            self.input_box.clear()
            self.input_box.setPlaceholderText("Could not hear you \u2014 try again")

    def _on_stt_error(self, error_msg: str):
        """Handle transcription failure."""
        self.mic_btn.set_recording(False)
        self.input_box.setEnabled(True)
        self.input_box.clear()
        self.input_box.setPlaceholderText("Mic error \u2014 try again")
        print(f"  \u274c STT Error: {error_msg}")

    # ── Status / send ────────────────────────────────────────────────────
    def set_status(self, msg: str):
        self.status_label.setText(msg)
        if msg == "Ready":
            self.input_box.setEnabled(True)
            self.input_box.setPlaceholderText("Ask Halo\u2026")
        else:
            self.input_box.setPlaceholderText(msg)

    def _on_send(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()
        self.input_box.clearFocus()
        self.set_status("Thinking\u2026")
        self._collapse()
        self.user_submitted.emit(text)


# --- Response Card (cursor-dodging) ------------------------------------------
class ResponseCard(QWidget):
    """
    Always-visible reply card that dodges the mouse cursor.
    Sits near a screen edge and smoothly slides to the opposite side
    whenever the cursor approaches, so it never blocks the user's clicks.
    Aliased as ChatPanel for backward-compat.
    """

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._setup_positions()
        self._start_dodge_timer()

        # Typewriter state
        self._type_timer = QTimer(self)
        self._type_timer.setSingleShot(True)
        self._type_timer.timeout.connect(self._type_tick)
        self._type_header = ""
        self._type_body_color = ""
        self._type_full_text = ""
        self._type_pos = 0

    def _build_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) 
        self.setFixedSize(CARD_W, CARD_MIN_H)
        _exclude_from_capture(self)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(6)

        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setFont(QFont(FONT_FAMILY, 11))
        self.history.setStyleSheet("""
            QTextEdit {
                background: transparent;
                color: rgba(255, 255, 255, 230);
                border: none;
                padding: 0px 4px;
                selection-background-color: rgba(255, 255, 255, 30);
            }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
                margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 35);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        root.addWidget(self.history, stretch=1)

        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont(FONT_FAMILY, 9))
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 100);")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.status_label)

    # -- Positioning -----------------------------------------------------------
    def _setup_positions(self):
        """Store screen bounds and place card at bottom-right."""
        screen = QApplication.primaryScreen().geometry()
        self._screen = screen
        start = QPoint(screen.width() - CARD_W - CARD_MARGIN,
                       screen.height() - CARD_MIN_H - CARD_MARGIN)
        self.move(start)

        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(350)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # -- Cursor dodge timer ----------------------------------------------------
    def _start_dodge_timer(self):
        self._dodge_timer = QTimer(self)
        self._dodge_timer.setInterval(100)   # check ~10 times/sec
        self._dodge_timer.timeout.connect(self._check_cursor)
        self._dodge_timer.start()

    def _check_cursor(self):
        """If the cursor is near the card, push the card away in 2D."""
        if self._anim.state() == QPropertyAnimation.State.Running:
            return

        cursor = QCursor.pos()
        geo = self.geometry()
        padded = geo.adjusted(-CARD_DODGE_PAD, -CARD_DODGE_PAD,
                              CARD_DODGE_PAD, CARD_DODGE_PAD)

        if not padded.contains(cursor):
            return

        # Vector from cursor → card centre (push card *away* from cursor)
        cx, cy = geo.center().x(), geo.center().y()
        dx = cx - cursor.x()
        dy = cy - cursor.y()
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        ux, uy = dx / length, dy / length       # unit direction

        target = self._dodge_target(ux, uy, cx, cy)

        # If the card would barely move (stuck against wall/corner), deflect
        if target is None:
            for angle_deg in (45, -45, 90, -90, 135, -135, 180):
                rad = math.radians(angle_deg)
                cos_a, sin_a = math.cos(rad), math.sin(rad)
                rx = ux * cos_a - uy * sin_a
                ry = ux * sin_a + uy * cos_a
                target = self._dodge_target(rx, ry, cx, cy)
                if target is not None:
                    break

        if target is not None:
            self._slide_to(target)

    # -- Dodge helpers ---------------------------------------------------------
    def _dodge_target(self, ux, uy, cx, cy):
        """Return a QPoint dodge destination for unit vector (ux, uy) from
        card-centre (cx, cy), or *None* if the move is too small (stuck)."""
        tx = int(cx + ux * CARD_DODGE_DIST - CARD_W / 2)
        ty = int(cy + uy * CARD_DODGE_DIST - CARD_MIN_H / 2)

        max_x = self._screen.width()  - CARD_W      - CARD_MARGIN
        max_y = self._screen.height() - CARD_MIN_H  - CARD_MARGIN
        tx = max(CARD_MARGIN, min(tx, max_x))
        ty = max(CARD_MARGIN, min(ty, max_y))

        move_dx = tx - self.pos().x()
        move_dy = ty - self.pos().y()
        if (move_dx * move_dx + move_dy * move_dy) ** 0.5 < CARD_STUCK_THRESH:
            return None
        return QPoint(tx, ty)

    def _slide_to(self, target: QPoint):
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(target)
        self._anim.start()

    # -- Paint: rounded rect ---------------------------------------------------
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        r = 12.0

        body = QPainterPath()
        body.addRoundedRect(0.0, 0.0, w, h, r, r)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(SPOT_GLASS_BASE))
        painter.drawPath(body)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(SPOT_GLASS_BORDER, 1.0))
        painter.drawPath(body)
        painter.end()

    def append_message(self, sender: str, text: str, color: str = "rgba(255,255,255,0.90)"):
        # Stop any in-progress typewriter
        self._type_timer.stop()

        sender_color = "rgba(255,255,255,0.50)" if sender == "Halo" else "rgba(255,255,255,0.35)"
        self._type_header = (
            f'<span style="color:{sender_color};font-size:9pt;font-weight:600;">{sender}</span><br>'
        )
        self._type_body_color = color
        self._type_full_text = text
        self._type_pos = 0

        # Show header immediately, body will be typed out
        self.history.clear()
        self.history.setHtml(self._type_header)
        self._type_tick()          # kick off first tick immediately

    def _type_tick(self):
        """Reveal the next chunk of characters."""
        if self._type_pos >= len(self._type_full_text):
            self._type_timer.stop()
            return

        chunk = random.randint(TYPE_MIN_CHARS, TYPE_MAX_CHARS)
        self._type_pos = min(self._type_pos + chunk, len(self._type_full_text))
        visible = self._type_full_text[:self._type_pos]

        self.history.setHtml(
            self._type_header
            + f'<span style="color:{self._type_body_color};font-size:11pt;">{visible}</span>'
        )

        # Schedule next tick with randomised delay
        delay = random.randint(TYPE_MIN_DELAY, TYPE_MAX_DELAY)
        self._type_timer.start(delay)

    def set_status(self, msg: str):
        self.status_label.setText(msg)


ChatPanel = ResponseCard


# ─── Hotkey Bridge ────────────────────────────────────────────────────────────
class _HotkeyBridge(QObject):
    """
    Thin QObject used to relay global keyboard hotkey events (which fire on a
    background thread) safely into the Qt main thread via queued signals.
    """
    send_pressed  = pyqtSignal()   # Alt+N — advance / start session
    reset_pressed = pyqtSignal()   # Alt+R — reset session


# ─── Top-Level Application Controller ────────────────────────────────────────
class HaloApp(QObject):
    """
    Owns and wires OverlayWindow + SpotlightBar + ResponseCard + AIWorker.

    Inherits QObject so that signal connections from AIWorker (a QThread) are
    automatically queued onto the main thread — required for safe GUI updates.

    Session flow (per SSOT §3):
      1. User types a prompt and presses Enter (or Alt+N) → first step.
      2. User acts on the highlighted element, then presses Alt+N → next step
         (no new prompt; Session memory carries context forward).
      3. Alt+R resets the session and clears the highlight.

    self.chat is an alias for self.card (ResponseCard) for backward-compat.
    Lifecycle: instantiate, then call .start().
    """

    def __init__(self):
        super().__init__()
        self.overlay = OverlayWindow()
        self.bar     = SpotlightBar()     # self-positions at top-centre
        self.card    = ResponseCard()     # self-positions at right edge
        self.chat    = self.card           # backward-compat alias
        self._worker: AIWorker | None = None

        # Tell overlay not to dim over the bar and card
        self.overlay._exclude_widgets = [self.bar, self.card]

        # Session state
        self._session         = Session()
        self._session_started = False     # True after the first step is fired

        # Hotkey bridge (routes keyboard thread → Qt main thread)
        self._bridge = _HotkeyBridge()
        self._bridge.send_pressed.connect(self._hotkey_send)
        self._bridge.reset_pressed.connect(self._hotkey_reset)

        # TTS state
        self._tts_worker: TTSWorker | None = None

        self.bar.user_submitted.connect(self._on_user_prompt)

    def start(self):
        self.overlay.show()
        self.bar.show()
        self.card.show()
        # Ensure bar & card render above the dim overlay
        self.bar.raise_()
        self.card.raise_()
        self.card.append_message(
            "Halo",
            "Hello! I'm here to help you navigate. What do you need?\n\n"
            "Tip: press Alt+N after each action to continue.",
        )

        # Register global hotkeys (silently skipped in headless/non-admin envs)
        try:
            keyboard.add_hotkey("alt+n", self._bridge.send_pressed.emit, suppress=True)
            keyboard.add_hotkey("alt+r", self._bridge.reset_pressed.emit, suppress=True)
        except Exception:
            pass

    # ── Private ──────────────────────────────────────────────────────────────
    def _on_user_prompt(self, prompt: str):
        """Enter/submit from SpotlightBar — begins (or restarts) a session."""
        self._session_started = True
        self._run_worker(SCREENSHOT_PATH, prompt)

    def _hotkey_send(self):
        """Alt+N — advance the session (or start it using the bar's text)."""
        if self._worker and self._worker.isRunning():
            return   # still processing previous step

        if not self._session_started:
            # Grab whatever text is in the input bar and submit it
            text = self.bar.input_box.text().strip()
            if text:
                self.bar._on_send()  # triggers _on_user_prompt via signal
            return

        # Auto-continue: no new prompt — Session memory provides context
        self.bar.set_status("Thinking…")
        self.card.set_status("Thinking…")
        self._capture_screenshot()
        self._run_worker(SCREENSHOT_PATH, None)

    def _hotkey_reset(self):
        """Alt+R — discard the current session and clear all highlights."""
        self._stop_tts()              # stop any voice playback
        self._session         = Session()
        self._session_started = False
        self.overlay.clear_highlight()
        self.bar.set_status("Ready")
        self.card.set_status("Ready")
        self.card.append_message("Halo", "Session reset. What would you like to do?")

    def _run_worker(self, screenshot_path: str, prompt: str | None):
        """Spin up an AIWorker for one pipeline step."""
        self._stop_tts()              # interrupt voice if still speaking
        self._capture_screenshot()
        self._worker = AIWorker(screenshot_path, prompt, session=self._session)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _capture_screenshot(self):
        """Take a full-screen screenshot and save to SCREENSHOT_PATH."""
        with mss.mss() as sct:
            sct.shot(mon=1, output=SCREENSHOT_PATH)

    def _on_result(self, result: dict):
        import threading
        print(f"[HALO] _on_result called on thread={threading.current_thread().name}  "
              f"status={result.get('status')}  coords=({result.get('x')},{result.get('y')},"
              f"{result.get('width')},{result.get('height')})")
        if result.get("status") == "success":
            self.overlay.show_highlight(
                result["x"], result["y"],
                result["width"], result["height"],
            )
            self.card.append_message("Halo", result["message"])
            self.bar.set_status("Press Alt+N after acting")
            self.card.set_status("Press Alt+N after acting")
            # Read the response aloud via ElevenLabs TTS
            self._speak(result["message"])
        else:
            msg = result.get("message", "Something went wrong. Please try again.")
            self.card.append_message("Halo", msg, "rgba(255,69,58,0.75)")
            self.bar.set_status("Ready")
            self.card.set_status("Ready")

    def _on_error(self, error_msg: str):
        self.card.append_message("Halo", f"[Error] {error_msg}", "rgba(255,69,58,0.75)")
        self.bar.set_status("Ready")
        self.card.set_status("Ready")

    # ── TTS helpers ──────────────────────────────────────────────────────
    def _speak(self, text: str):
        """Start TTS playback in a background thread."""
        self._stop_tts()          # cancel any in-flight playback first
        self._tts_worker = TTSWorker(text)
        self._tts_worker.started_speaking.connect(self._on_tts_started)
        self._tts_worker.finished_speaking.connect(self._on_tts_finished)
        self._tts_worker.error.connect(self._on_tts_error)
        self._tts_worker.start()

    def _stop_tts(self):
        """Interrupt any running TTS playback."""
        if self._tts_worker is not None and self._tts_worker.isRunning():
            self._tts_worker.request_stop()

    def _on_tts_started(self):
        print("  🔊 TTS speaking…")

    def _on_tts_finished(self):
        print("  🔊 TTS done.")

    def _on_tts_error(self, msg: str):
        print(f"  ❌ TTS Error: {msg}")


# ─── Entry Point ──────────────────────────────────────────────────────────────
def main():
    # Allow Ctrl+C in the terminal to kill the process cleanly
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("Halo")
    app.setWindowIcon(QIcon(str(_ICON_PATH)))

    halo = HaloApp()
    halo.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
