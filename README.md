# Halo

A digital guide that act as a GPS for everything on the desktop for the Mistral AI hackathon. Halo empowers elderly users through a spotlight highlighting system that directs focus to key on-screen elements. It features a macOS-Spotlight-style input bar for natural-language queries, delivering AI-generated assistance via an intuitive overlay that stays clear of the cursor.

## Architecture

| Component         | Role                                                                          |
| ----------------- | ----------------------------------------------------------------------------- |
| **OverlayWindow** | Full-screen click-through scrim with pulsating highlight cutout               |
| **SpotlightBar**  | Drop down input bar (collapse/expand, bounce animation)                    |
| **ResponseCard**  |  Reply card with typewriter effect                              |
| **AIWorker**      | Background QThread — wraps `ai_brain.Session.next_step()` for multi-step flow |
| **HaloApp**       | Top-level wiring; owns the active Session and all windows                     |
| **ai_brain/**     | AI/vision package: OpenCV edge detection → Mistral VLM reasoning              |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Mistral API key and ElevenLabs API key.

```
MISTRAL_API_KEY=your_key_here
ELEVENLABS_API_KEY=you_key_here
```

## Run

```bash
python overlay_ui.py
```

### Controls

A pill-shaped button sits on the right edge of the screen with two icons:

| Button         | Action                                            |
| -------------- | ------------------------------------------------- |
| play  | Take a screenshot and advance to the next AI step |
| reset | Reset the session and clear the highlight         |

**Typical flow:**
1. Type your goal or click the mic button in the Spotlight bar (e.g. "I can't remember my password") and press Enter.
2. Halo highlights the correct element. Take the suggested action.
3. Click the play button on the right edge  and Halo sees the updated screen and guides you to the next step.
4. Repeat until done. Click reset button to start a new task.

## Test

```bash
pytest tests/ --tb=short -q
```

## Project Structure

```text
.
├── overlay_ui.py           Main UI layer (overlay, spotlight bar, response card, hotkeys)
├── ai_brain/
│   ├── __init__.py         Re-exports public API
│   ├── ai_brain.py         Orchestrator: OpenCV → Mistral → coordinates
│   ├── opencv_detect.py    Vision engine: Canny edge detection + numbered bounding boxes
│   ├── mistral_label.py    Reasoning engine: Mistral VLM API calls
│   ├── session.py          Multi-step session with conversation memory
│   └── prompt.txt          System prompt injected into every Mistral call
├── MockPages/              Local HTML/CSS mock pages for controlled demo testing
├── requirements.txt        Dependencies
├── tests/                  142 automated tests + manual integration scripts
├── icons/                  SVG assets (halo_logo.svg)
└── images/                 Runtime screenshots (gitignored)
```

## Key Design Decisions

- **Session memory** — `Session.next_step()` keeps the full Mistral chat history alive so the model understands "what comes next" after each user action.
- **OpenCV vision pass** — Canny edge detection draws numbered RED boxes over all detected UI elements; the annotated image is sent to Mistral alongside the raw screenshot for accurate targeting.
- **Click-through overlay** — uses the Windows `WindowTransparentForInput` flag so clicks pass through the scrim to apps underneath.
- **Responsive message card** — the ResponseCard computes a 2D dodge vector and deflects in 45° steps to escape corners.
- **Typewriter effect** — AI responses stream character-by-character with randomised timing for a natural feel.
- **Capture exclusion** — all Halo windows are hidden from `PrintScreen`, OBS, and other capture tools.

