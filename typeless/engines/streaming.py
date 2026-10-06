"""Live dictation loop shared by the local engines.

The microphone fills a buffer; Silero VAD marks speech. While a phrase is spoken the
buffer is re-recognised every STEP_S and LocalAgreement confirms words two passes agree
on. A pause of END_SILENCE_S ends the phrase: one last pass confirms the rest and the
buffer is emptied, so passes only ever see the current phrase. In silence nothing runs.
"""

from __future__ import annotations

import gc
import logging
import queue
import threading
import time

import numpy as np

from ..agreement import LocalAgreement, Word, continue_sentence, join_words, trim_point
from ..config import Config
from ..loudness import loudness
from .base import Engine

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
STEP_S = 0.4  # minimum time between passes while speaking
END_SILENCE_S = 0.5  # a pause this long ends the phrase
PRE_ROLL_S = 0.3  # audio kept before speech starts: VAD reacts a frame or two late
MIN_AUDIO_S = 0.3
SOFT_BUFFER_S = 3.0  # beyond this, trim at the last confirmed sentence/clause end
HARD_BUFFER_S = 6.0  # beyond this, trim at the last confirmed word even mid-sentence
CONTEXT_S = 1.0  # confirmed audio kept before a trim: the model hears the words before the cut
SLOW_PASS_S = 2.0  # log passes slower than this


class StreamingEngine(Engine):
    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._model = None
        self._model_lock = threading.Lock()
        self._chunks: queue.Queue[np.ndarray] = queue.Queue()
        self._stream = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._released = False  # shut down: don't keep (or finish loading) a model
        self._vad = None

    # --- for subclasses ------------------------------------------------------
    @property
    def model_name(self) -> str:
        raise NotImplementedError

    def _load(self):
        """Load the speech model (runs once, in a background thread)."""
        raise NotImplementedError

    def _recognize(self, model, audio: np.ndarray, offset: float, context: str, final: bool) -> list[Word]:
        """Words with absolute times (offset = time of audio[0]); context = text said before."""
        raise NotImplementedError

    # --- model -------------------------------------------------------------
    def preload(self) -> None:
        threading.Thread(target=self._ensure_model, name="model-load", daemon=True).start()

    def _ensure_model(self):
        with self._model_lock:
            if self._model is None:
                from ..vad import SpeechDetector

                self.status.emit("Загрузка модели…")
                t = time.monotonic()
                self._vad = SpeechDetector()
                model = self._load()
                # The first pass is slower (allocations, caches): pay it now, not on the first phrase.
                warm = np.random.default_rng(0).normal(0, 0.01, SAMPLE_RATE).astype(np.float32)
                self._recognize(model, warm, 0.0, "", final=False)
                self._model = model
                log.info("model %s loaded in %.1fs", self.model_name, time.monotonic() - t)
                self.status.emit("")
            if self._released:  # replaced while loading: don't keep it alive
                self._model = None
            return self._model

    # --- control -----------------------------------------------------------
    def start(self) -> None:
        # Opening the microphone takes ~0.5 s: do it on the worker so the UI reacts instantly.
        self._chunks = queue.Queue()
        self._stop.clear()
        self._worker = threading.Thread(target=self._session, name="dictation", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()

    def _open_stream(self) -> bool:
        import sounddevice as sd

        try:
            self._stream = sd.InputStream(
                # 32 ms blocks: one VAD frame, and ~30 waveform level updates a second
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=512,
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
        """Stop and free the model: switching models used to keep the old one in RAM."""
        self.stop()
        self._released = True
        worker = self._worker
        if worker is not None and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=5)
        # If a load is in progress, don't block the UI: _ensure_model drops it when done.
        if self._model_lock.acquire(blocking=False):
            try:
                self._model = None
            finally:
                self._model_lock.release()
        gc.collect()

    def _on_audio(self, data, frames, time_info, status) -> None:
        mono = data[:, 0].copy()
        self._chunks.put(mono)
        rms = float(np.sqrt(np.mean(mono * mono)))
        self.level.emit(loudness(rms))

    # --- streaming loop ----------------------------------------------------
    def _drain(self) -> np.ndarray:
        parts = []
        while True:
            try:
                parts.append(self._chunks.get_nowait())
            except queue.Empty:
                return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)

    def _pass(self, model, agreement: LocalAgreement, buffer: np.ndarray, offset: float,
              final: bool) -> list[Word]:
        # Only text whose audio is no longer in the buffer: if the context repeats what the
        # model is about to hear, Whisper skips those words in the audio.
        before = join_words([w for w in agreement.committed if w.end <= offset][-30:])
        started = time.monotonic()
        words = self._recognize(model, buffer, offset, before, final)
        took = time.monotonic() - started
        if took > SLOW_PASS_S:
            log.warning("slow pass: %.1fs for %.1fs of audio", took, len(buffer) / SAMPLE_RATE)
        return words

    def _emit(self, words: list[Word]) -> None:
        text = join_words(words)
        if text:
            self.final.emit(text)

    def _run(self) -> None:
        try:
            model = self._ensure_model()
            vad = self._vad
            vad.reset()
            agreement = LocalAgreement()
            buffer = np.zeros(0, dtype=np.float32)
            offset = 0.0  # absolute time of buffer[0]
            in_phrase = False  # speech heard since the last phrase ended
            last_voice = 0.0  # absolute time the last speech frame ended
            phrase_start = True  # next confirmed words open a phrase

            def emit(words: list[Word]) -> None:
                nonlocal phrase_start
                if phrase_start and words:
                    before = agreement.committed[:-len(words)]
                    words = continue_sentence(before[-1].text if before else "", words)
                    phrase_start = False
                self._emit(words)

            def end_phrase() -> None:
                nonlocal phrase_start
                if len(buffer) >= MIN_AUDIO_S * SAMPLE_RATE:
                    emit(agreement.flush(self._pass(model, agreement, buffer, offset, final=True)))
                self.preview.emit("")
                phrase_start = True

            while True:
                stopping = self._stop.is_set()
                if stopping:
                    self._close_stream()
                started = time.monotonic()
                new = self._drain()
                t0 = offset + len(buffer) / SAMPLE_RATE
                flags = vad.feed(new)
                for i, speech in enumerate(flags):
                    if speech:
                        last_voice = t0 + (i + 1) * 512 / SAMPLE_RATE
                fresh = any(flags)
                buffer = np.concatenate([buffer, new])
                end = offset + len(buffer) / SAMPLE_RATE

                if stopping:
                    if in_phrase or fresh:
                        end_phrase()
                    break

                if fresh:
                    in_phrase = True
                if not in_phrase:
                    keep = int(PRE_ROLL_S * SAMPLE_RATE)  # silence between phrases: keep a little
                    if len(buffer) > keep:
                        offset += (len(buffer) - keep) / SAMPLE_RATE
                        buffer = buffer[-keep:]
                elif end - last_voice >= END_SILENCE_S:
                    end_phrase()
                    in_phrase = False
                    keep = int(PRE_ROLL_S * SAMPLE_RATE)
                    offset += max(0, len(buffer) - keep) / SAMPLE_RATE
                    buffer = buffer[-keep:]
                elif fresh and len(buffer) >= MIN_AUDIO_S * SAMPLE_RATE:
                    words = self._pass(model, agreement, buffer, offset, final=False)
                    confirmed, tail = agreement.update(words)
                    emit(confirmed)
                    self.preview.emit(join_words(tail))
                    # Drop confirmed audio so passes stay fast in a long phrase.
                    cut_at = trim_point(agreement.committed, offset, len(buffer) / SAMPLE_RATE,
                                        SOFT_BUFFER_S, HARD_BUFFER_S)
                    if cut_at is not None:
                        keep_from = max(offset, cut_at - CONTEXT_S)
                        cut = int((keep_from - offset) * SAMPLE_RATE)
                        if cut > 0:
                            buffer = buffer[cut:]
                            offset += cut / SAMPLE_RATE
                self._stop.wait(max(0.0, STEP_S - (time.monotonic() - started)))
        except Exception as e:
            log.exception("transcription failed")
            self.error.emit(f"Ошибка распознавания: {e}")
        finally:
            self._close_stream()
            self.stopped.emit()
