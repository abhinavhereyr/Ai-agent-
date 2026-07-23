"""Voice module - Speech-to-text and text-to-speech."""
import io
import json
import os
import queue
import tempfile
import threading
import time

import numpy as np

from core.config import config

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    from scipy.io.wavfile import write as write_wav
except ImportError:
    write_wav = None

try:
    import soundfile as sf
except ImportError:
    sf = None


# ---------------------------------------------------------------------------
# STT - Speech to Text (using transformers Whisper)
# ---------------------------------------------------------------------------

class STTEngine:
    """Speech-to-text using local Whisper model via transformers."""

    def __init__(self, model_name=None):
        self.model_name = model_name or f"openai/whisper-{config.get('voice', 'stt_model', default='tiny')}"
        self.pipe = None
        self._lock = threading.Lock()
        self.sample_rate = 16000

    def _ensure_model(self):
        if self.pipe is None:
            with self._lock:
                if self.pipe is None:  # double-check
                    try:
                        from transformers import pipeline
                    except ImportError:
                        raise RuntimeError("transformers not installed. Run: pip install transformers")
                    print(f"[STT] Loading model: {self.model_name}")
                    self.pipe = pipeline(
                        "automatic-speech-recognition",
                        model=self.model_name,
                        device=-1,  # CPU
                    )

    def transcribe(self, audio_path):
        """Transcribe an audio file to text."""
        self._ensure_model()
        result = self.pipe(audio_path)
        return result.get("text", "").strip()

    def transcribe_numpy(self, audio_array):
        """Transcribe a numpy audio array (samplerate=16000)."""
        self._ensure_model()
        result = self.pipe(audio_array)
        return result.get("text", "").strip()

    def record_and_transcribe(self, duration=5, sample_rate=16000):
        """Record from microphone and transcribe."""
        if sd is None:
            raise RuntimeError("sounddevice not installed")
        print(f"[STT] Recording for {duration}s...")
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype=np.float32)
        sd.wait()
        audio = recording.flatten()
        return self.transcribe_numpy(audio)


# ---------------------------------------------------------------------------
# TTS - Text to Speech
# ---------------------------------------------------------------------------

class TTSEngine:
    """Text-to-speech using system commands (espeak/ffplay) or simple beep fallback."""

    def __init__(self):
        self.enabled = config.get("voice", "tts_enabled")
        self._check_backend()

    def _check_backend(self):
        # Check for available TTS backends
        for cmd in ["espeak", "say", "festival"]:
            if os.system(f"which {cmd} 2>/dev/null") == 0:
                self.backend = cmd
                return
        # Check if we can use python
        try:
            import pyttsx3
            self.backend = "pyttsx3"
            return
        except ImportError:
            pass
        self.backend = "none"

    def say(self, text):
        """Speak text aloud."""
        if not self.enabled:
            return
        if not text:
            return
        # Escape quotes for shell
        safe = text.replace('"', '\\"')
        if self.backend == "espeak":
            threading.Thread(target=lambda: os.system(f'espeak "{safe}" 2>/dev/null'), daemon=True).start()
        elif self.backend == "pyttsx3":
            import pyttsx3
            threading.Thread(target=lambda: self._pyttsx3_say(text), daemon=True).start()
        else:
            # Fallback: print
            print(f"[TTS] {text}")

    def _pyttsx3_say(self, text):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Wake Word Detection (simple keyword spotting)
# ---------------------------------------------------------------------------

class WakeWordDetector:
    """Simple wake word detection using keyword matching on STT output."""

    def __init__(self, wake_word=None):
        self.wake_word = wake_word or config.get("voice", "wake_word", default="hey agent").lower()
        self.stt = STTEngine()
        self.listening = False

    def listen_for_wake_word(self, timeout=30):
        """Keep recording short clips until wake word is detected."""
        print(f"[Wake] Listening for '{self.wake_word}'...")
        chunk_duration = 2  # seconds
        max_attempts = int(timeout / chunk_duration) if timeout else 9999

        for _ in range(max_attempts):
            try:
                text = self.stt.record_and_transcribe(duration=chunk_duration, sample_rate=16000)
                print(f"[Wake] Heard: {text}")
                if self.wake_word in text.lower():
                    print("[Wake] Wake word detected!")
                    return True
            except Exception as e:
                print(f"[Wake] Error: {e}")
                time.sleep(0.5)
        return False


# ---------------------------------------------------------------------------
# Audio utilities
# ---------------------------------------------------------------------------

def list_microphones():
    """List available audio input devices."""
    if sd is None:
        return []
    devices = sd.query_devices()
    inputs = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            inputs.append({"id": i, "name": dev["name"]})
    return inputs


def record_audio(duration=5, samplerate=16000):
    """Record audio and return numpy array."""
    if sd is None:
        raise RuntimeError("sounddevice not installed")
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype=np.float32)
    sd.wait()
    return recording.flatten()


def save_audio(audio_array, path, samplerate=16000):
    """Save numpy audio array to WAV file."""
    if sf:
        sf.write(path, audio_array, samplerate)
    elif write_wav:
        write_wav(path, samplerate, (audio_array * 32767).astype(np.int16))
    else:
        raise RuntimeError("No audio writing library available")


_stt = None
_tts = None


def __getattr__(name):
    if name == "stt":
        global _stt
        if _stt is None:
            _stt = STTEngine()
        return _stt
    if name == "tts":
        global _tts
        if _tts is None:
            _tts = TTSEngine()
        return _tts
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
