# :page_facing_up: Single Source of Truth (SSOT): Project "ClearPath"

## 1. The Narrative & Scope

* **The Problem:** The modern digital world strips the elderly of their independence. Simple roadblocks—like forgetting a password—force them to rely constantly on family members or caregivers to access basic services like banking. This creates a painful cycle: the elderly feel helpless and lose their autonomy, while caregivers are burdened with the repetitive, frustrating task of acting as permanent tech support.
* **The Solution:** A localized, contextual AI overlay that acts as a patient digital guide. It gives autonomy back to the user by "seeing" the screen and physically drawing a glowing box around the exact next step, teaching them how to navigate the digital world themselves and eliminating the need to call their kids for help.
* **Demo Target:** A custom-built, local HTML/CSS mock "Bank Login" page. This guarantees a controlled environment where the "Forgot Password" and "Submit" triggers are styled as clean, geometric shapes that our vision engine can detect with 100% reliability and zero latency.

## 2. The Tech Stack

* **Core Language:** Python 3.10+
* **Frontend (The Glass):** `PyQt6` (Creates the transparent, frameless, always-on-top overlay and chat widget).
* **Screen Capture:** `mss` (Lightning-fast cross-platform screenshots).
* **Vision Engine:** `OpenCV` (`cv2`). Tuned specifically for clean web UI edge-detection (high accuracy, zero latency). **No OCR required** due to the controlled mock environment.
* **Reasoning Engine:** Mistral API (Pixtral VLM) for semantic understanding of the marked-up screen and empathetic response generation.

## 3. The Architecture & Interaction Flow

This system is strictly decoupled into a "Client" (UI) and a "Server" (AI Logic) to prevent merge conflicts and allow parallel development.

1. **Invocation:** User types "I can't remember my password" into the floating PyQt6 chat widget.
2. **Capture:** UI thread takes a screenshot (`images/raw.png`) and passes it to the AI worker thread.
3. **Vision Pass:** OpenCV converts `raw.png` to grayscale, runs edge detection, and draws a numbered box over every button-like shape. Saves as `images/marked.png`.
4. **Reasoning Pass:** `marked.png` and the user's prompt are sent to Mistral. Mistral's System Prompt forces it to act as a patient guide and reply with *only* the correct box ID number.
5. **Resolution:** The AI thread maps the ID back to the OpenCV coordinates and returns them to the UI thread. The PyQt6 app draws a glowing neon box over the target element.

## 4. The Internal API Contract

The UI (`overlay_ui.py`) and the Brain (`ai_brain.py`) will communicate using this exact data structure.

**Function Signature (in `ai_brain.py`):**

```python
def get_target_coordinates(screenshot_path: str, user_prompt: str) -> dict:

```

**Guaranteed Output Schema:**

```json
{
    "status": "success", 
    "x": 380, 
    "y": 450, 
    "width": 150, 
    "height": 30, 
    "message": "Don't worry, let's reset it together. Click the 'Forgot Password' link I highlighted in red for you."
}

```

---