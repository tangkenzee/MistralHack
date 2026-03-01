"""
speech_to_text.py
─────────────────
Speech-to-Text Engine: Records audio from the microphone and transcribes it
in real time using the Mistral Voxtral Realtime Transcription API.

Pipeline (realtime):
  1. Open the microphone via PyAudio and yield PCM chunks asynchronously.
  2. Stream chunks to `client.audio.realtime.transcribe_stream()` using
     the `voxtral-mini-transcribe-realtime-2602` model.
  3. As `TranscriptionStreamTextDelta` events arrive, invoke a callback
     with each text fragment so the UI can show live captions.
  4. When the user stops recording, close the mic iterator which causes
     the stream to emit `TranscriptionStreamDone`.
"""

import os
import asyncio
from typing import AsyncIterator, Callable

import pyaudio
from dotenv import load_dotenv
from mistralai import Mistral
from mistralai.extra.realtime import UnknownRealtimeEvent
from mistralai.models import (
    AudioFormat,
    RealtimeTranscriptionError,
    RealtimeTranscriptionSessionCreated,
    TranscriptionStreamDone,
    TranscriptionStreamTextDelta,
)

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# ── Audio recording settings ─────────────────────────────────────────────────
SAMPLE_RATE       = 16000   # 16 kHz – standard for speech recognition
CHANNELS          = 1       # mono
CHUNK_DURATION_MS = 480     # chunk length sent to Voxtral (ms)
AUDIO_FORMAT      = AudioFormat(encoding="pcm_s16le", sample_rate=SAMPLE_RATE)


async def _iter_microphone(
    sample_rate: int,
    chunk_duration_ms: int,
    stop_event: asyncio.Event,
) -> AsyncIterator[bytes]:
    """
    Yield microphone PCM chunks (16-bit mono) until *stop_event* is set.
    The blocking `stream.read` call is offloaded to an executor so the
    asyncio loop is never stalled.
    """
    pa = pyaudio.PyAudio()
    chunk_samples = int(sample_rate * chunk_duration_ms / 1000)

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=sample_rate,
        input=True,
        frames_per_buffer=chunk_samples,
    )

    loop = asyncio.get_running_loop()
    try:
        while not stop_event.is_set():
            data = await loop.run_in_executor(
                None, stream.read, chunk_samples, False,
            )
            yield data
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


async def realtime_transcribe(
    stop_event: asyncio.Event,
    on_delta: Callable[[str], None],
    on_done: Callable[[], None],
    on_error: Callable[[str], None],
) -> None:
    """
    Stream microphone audio to Voxtral Realtime and invoke callbacks
    as transcription text deltas arrive.

    Args:
        stop_event: Set this to signal the microphone to stop.
        on_delta:   Called with each incremental text fragment.
        on_done:    Called once the transcription stream finishes.
        on_error:   Called with an error message on failure.
    """
    if not MISTRAL_API_KEY or MISTRAL_API_KEY == "your_mistral_api_key_here":
        on_error("MISTRAL_API_KEY not set — cannot transcribe audio.")
        return

    client = Mistral(api_key=MISTRAL_API_KEY)
    audio_stream = _iter_microphone(SAMPLE_RATE, CHUNK_DURATION_MS, stop_event)

    try:
        async for event in client.audio.realtime.transcribe_stream(
            audio_stream=audio_stream,
            model="voxtral-mini-transcribe-realtime-2602",
            audio_format=AUDIO_FORMAT,
        ):
            if isinstance(event, RealtimeTranscriptionSessionCreated):
                print("  🎤 Realtime session created.")
            elif isinstance(event, TranscriptionStreamTextDelta):
                on_delta(event.text)
            elif isinstance(event, TranscriptionStreamDone):
                print("  ✅ Transcription stream done.")
                on_done()
                return
            elif isinstance(event, RealtimeTranscriptionError):
                on_error(str(event))
                return
            elif isinstance(event, UnknownRealtimeEvent):
                continue
    except Exception as exc:
        on_error(str(exc))
