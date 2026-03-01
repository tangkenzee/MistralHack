# Halo

An always-on-top, transparent overlay assistant built with **PyQt6** for the Mistral AI hackathon.  
Halo helps elderly users by highlighting on-screen elements through a dim scrim with a clear cutout, accepting natural-language queries via a macOS-Spotlight-style input bar, and displaying AI responses in a cursor-dodging card.

## Architecture

| Component         | Role                                                                          |
| ----------------- | ----------------------------------------------------------------------------- |
| **OverlayWindow** | Full-screen click-through scrim with pulsating highlight cutout               |
| **SpotlightBar**  | iPhone-notch input bar (collapse/expand, bounce animation)                    |
| **ResponseCard**  | Cursor-dodging reply card with typewriter effect                              |
| **AIWorker**      | Background QThread — wraps `ai_brain.Session.next_step()` for multi-step flow |
| **_HotkeyBridge** | QObject that relays global keyboard hotkeys to the Qt main thread             |
| **HaloApp**       | Top-level wiring; owns the active Session and all windows                     |
| **ai_brain/**     | AI/vision package: OpenCV edge detection → Mistral VLM reasoning              |

All windows use `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` so the overlay is invisible to screen recordings and screenshots.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Mistral API key:

```
MISTRAL_API_KEY=your_key_here
```

## Run

```bash
python overlay_ui.py
```

### Hotkeys

| Key     | Action                                                             |
| ------- | ------------------------------------------------------------------ |
| `Alt+N` | Take a screenshot and run the AI pipeline (repeat after each step) |
| `Alt+R` | Reset the session and clear the highlight                          |

**Typical flow:**
1. Type your goal in the Spotlight bar (e.g. "I can't remember my password") and press Enter.
2. Halo highlights the correct element. Take the suggested action.
3. Press `Alt+N` — Halo sees the updated screen and guides you to the next step.
4. Repeat until done. Press `Alt+R` to start a new task.

## Test

```bash
pytest tests/ --tb=short -q
```

## Project Structure

```
overlay_ui.py           Main UI layer (overlay, spotlight bar, response card, hotkeys)
ai_brain/               AI/vision package
  __init__.py             Re-exports public API
  ai_brain.py             Orchestrator: OpenCV → Mistral → coordinates
  opencv_detect.py        Vision engine: Canny edge detection + numbered bounding boxes
  mistral_label.py        Reasoning engine: Mistral VLM API calls
  session.py              Multi-step session with conversation memory
  prompt.txt              System prompt injected into every Mistral call
MockPages/              Local HTML/CSS mock pages for controlled demo testing
requirements.txt        Dependencies
tests/                  142 automated tests + manual integration scripts
icons/                  SVG assets (halo_logo.svg)
images/                 Runtime screenshots (gitignored)
```

## Key Design Decisions

- **Session memory** — `Session.next_step()` keeps the full Mistral chat history alive so the model understands "what comes next" after each user action.
- **OpenCV vision pass** — Canny edge detection draws numbered RED boxes over all detected UI elements; the annotated image is sent to Mistral alongside the raw screenshot for accurate targeting.
- **Click-through overlay** — uses the Windows `WindowTransparentForInput` flag so clicks pass through the scrim to apps underneath.
- **Cursor dodging** — the ResponseCard computes a 2D dodge vector and deflects in 45° steps to escape corners.
- **Typewriter effect** — AI responses stream character-by-character with randomised timing for a natural feel.
- **Capture exclusion** — all Halo windows are hidden from `PrintScreen`, OBS, and other capture tools.

