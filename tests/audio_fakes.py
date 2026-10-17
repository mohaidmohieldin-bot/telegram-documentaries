"""Build real, tiny WAV files for tests (24 kHz mono 16-bit, like Gemini TTS)."""

import io
import wave

SAMPLE_RATE = 24_000


def make_wav(seconds: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"\x00\x00" * int(SAMPLE_RATE * seconds))
    return buffer.getvalue()
