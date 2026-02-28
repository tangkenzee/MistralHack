# Halo

An always-on-top, transparent overlay assistant built with **PyQt6** for the Mistral AI hackathon.  
Halo helps elderly users by highlighting on-screen elements through a dim scrim with a clear cutout, accepting natural-language queries via a macOS-Spotlight-style input bar, and displaying AI responses in a cursor-dodging card.

## Architecture

| Component         | Role                                                            |
| ----------------- | --------------------------------------------------------------- |
| **OverlayWindow** | Full-screen click-through scrim with pulsating highlight cutout |
| **SpotlightBar**  | iPhone-notch input bar (collapse/expand, bounce animation)      |
| **ResponseCard**  | Cursor-dodging reply card with typewriter effect                |
| **AIWorker**      | Background QThread — delegates to `ai_brain.py`                 |
| **HaloApp**       | Top-level wiring that owns all windows                          |

All windows use `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` so the overlay is invisible to screen recordings and screenshots.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Run

```bash
python overlay_ui.py
```

## Test

```bash
pytest tests/ --tb=short -q
```

## Project Structure

```
overlay_ui.py       Main UI layer (overlay, spotlight bar, response card)
ai_brain.py         AI/vision stub (returns hardcoded result for now)
requirements.txt    Dependencies
tests/              142 tests covering all UI components
icons/              SVG assets (halo_logo.svg)
images/             Runtime screenshots (gitignored)
```

## Key Design Decisions

- **Click-through overlay** — uses the Windows `WindowTransparentForInput` flag so clicks pass through the scrim to apps underneath.
- **Cursor dodging** — the ResponseCard computes a 2D dodge vector from the cursor and deflects in 45° steps to escape corners.
- **Typewriter effect** — AI responses stream character-by-character with randomised timing for a natural feel.
- **Capture exclusion** — all Halo windows are hidden from `PrintScreen`, OBS, and other capture tools.
