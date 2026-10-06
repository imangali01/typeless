"""Local streaming dictation with faster-whisper on CPU.

The microphone fills an audio buffer; a worker thread re-transcribes it every STEP_S
and LocalAgreement confirms words that two consecutive passes agree on.
"""

from __future__ import annotations

import logging
import queue
import threading
import time

import numpy as np

from ..agreement import LocalAgreement, Word, join_words
from ..config import Config
from ..languages import DEFAULT_LANGUAGE, LANGUAGE_MODES, build_prompt
from .base import Engine

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
STEP_S = 0.6  # minimum time between transcription passes
MAX_BUFFER_S = 12.0  # trim confirmed audio once the buffer grows beyond this
MIN_AUDIO_S = 0.5


class WhisperEngine(Engine):
    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._model = None
        self._model_lock = threading.Lock()
        self._chunks: queue.Queue[np.ndarray] = queue.Queue()
        self._stream = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()

    # --- model -------------------------------------------------------------
    def preload(self) -> None:
        threading.Thread(target=self._ensure_model, name="whisper-load", daemon=True).start()

    def _ensure_model(self):
        with self._model_lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                self.status.emit("Загрузка модели…")
                t = time.monotonic()
                self._model = WhisperModel(
                    self.config.whisper_model, device="cpu", compute_type="int8", cpu_threads=8
                )
                log.info("model %s loaded in %.1fs", self.config.whisper_model, time.monotonic() - t)
                self.status.emit("")
            return self._model

    # --- control -----------------------------------------------------------
    def start(self) -> None:
        # Opening the microphone takes ~0.5 s: do it on the worker so the UI reacts instantly.
        self._chunks = queue.Queue()
        self._stop.clear()
        self._worker = threading.Thread(target=self._session, name="whisper-stream", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()

    def _open_stream(self) -> bool:
        import sounddevice as sd

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=1600,
                callback=self._on_audio,
            )
            self._stream.start()
            return True
        except Exception as e:
            log.exception("microphone failed")
            self._stream = None
            self.error.emit(f"Микрофон недоступен: {e}")
            return False

    def _close_stream(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _session(self) -> None:
        if not self._open_stream():
            self.stopped.emit()
            return
        self.started.emit()
        self._run()

    def shutdown(self) -> None:
        self.stop()

    def _on_audio(self, data, frames, time_info, status) -> None:
        mono = data[:, 0].copy()
        self._chunks.put(mono)
        rms = float(np.sqrt(np.mean(mono * mono)))
        self.level.emit(min(1.0, rms * 12))

    # --- streaming loop ----------------------------------------------------
    def _drain(self, buffer: np.ndarray) -> np.ndarray:
        parts = [buffer]
        while True:
            try:
                parts.append(self._chunks.get_nowait())
            except queue.Empty:
                return np.concatenate(parts)

    def _prompt(self, agreement: LocalAgreement, offset: float) -> str:
        # Only text whose audio is no longer in the buffer: if the prompt repeats what the
        # model is about to hear, Whisper skips those words in the audio.
        before = [w for w in agreement.committed if w.end <= offset][-30:]
        return build_prompt(self.config.language_mode, self.config.profile,
                            self.config.dictionary, join_words(before))

    def _transcribe(self, audio: np.ndarray, offset: float, prompt: str) -> list[Word]:
        model = self._ensure_model()
        mode = LANGUAGE_MODES.get(self.config.language_mode, LANGUAGE_MODES[DEFAULT_LANGUAGE])
        segments, _ = model.transcribe(
            audio,
            language=mode.whisper,
            beam_size=1,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=prompt or None,
        )
        return [
            Word(offset + w.start, offset + w.end, w.word)
            for seg in segments
            for w in (seg.words or [])
        ]

    def _emit(self, words: list[Word]) -> None:
        text = join_words(words)
        if text:
            self.final.emit(text)

    def _run(self) -> None:
        agreement = LocalAgreement()
        buffer = np.zeros(0, dtype=np.float32)
        offset = 0.0  # absolute time of buffer[0]
        try:
            while not self._stop.is_set():
                started = time.monotonic()
                buffer = self._drain(buffer)
                if len(buffer) >= MIN_AUDIO_S * SAMPLE_RATE:
                    words = self._transcribe(buffer, offset, self._prompt(agreement, offset))
                    confirmed, tail = agreement.update(words)
                    self._emit(confirmed)
                    self.preview.emit(join_words(tail))
                    # Drop audio that is fully confirmed so passes stay fast.
                    if len(buffer) / SAMPLE_RATE > MAX_BUFFER_S and agreement.committed:
                        cut = int((agreement.committed_end - offset) * SAMPLE_RATE)
                        if cut > 0:
                            buffer = buffer[cut:]
                            offset = agreement.committed_end
                self._stop.wait(max(0.0, STEP_S - (time.monotonic() - started)))

            self._close_stream()
            buffer = self._drain(buffer)
            if len(buffer) >= 0.2 * SAMPLE_RATE:
                words = self._transcribe(buffer, offset, self._prompt(agreement, offset))
                self._emit(agreement.flush(words))
            self.preview.emit("")
        except Exception as e:
            log.exception("transcription failed")
            self.error.emit(f"Ошибка распознавания: {e}")
        finally:
            self._close_stream()
            self.stopped.emit()
