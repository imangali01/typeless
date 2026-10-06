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

from ..agreement import LocalAgreement, Word, join_words, trim_point
from ..config import Config
from ..languages import DEFAULT_LANGUAGE, LANGUAGE_MODES, build_prompt
from ..loudness import loudness
from .base import Engine

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
STEP_S = 0.5  # minimum time between transcription passes
SOFT_BUFFER_S = 6.0  # beyond this, trim at the last confirmed sentence/clause end
HARD_BUFFER_S = 10.0  # beyond this, trim at the last confirmed word even mid-sentence
MIN_AUDIO_S = 0.5
FINAL_BEAM = 5  # wider beam for the last pass, only when the tail is short
FINAL_BEAM_MAX_S = 3.0
CPU_THREADS = 4  # measured on i5-13420H: ~as fast as 8 threads at half the CPU load
SPEECH_RMS = 0.006  # below this a chunk is treated as silence
MAX_NEW_TOKENS = 200  # per pass; a 10 s buffer of fast speech is ~60-80 tokens
SLOW_PASS_S = 3.0  # log passes slower than this


def _looks_hallucinated(seg) -> bool:
    """A segment that repeats itself ("что я не знаю, что я не знаю, …") or is
    low-confidence text over what the model itself calls silence."""
    if seg.compression_ratio > 2.4:
        return True
    return seg.no_speech_prob > 0.6 and seg.avg_logprob < -1.0


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
                    self.config.whisper_model, device="cpu", compute_type="int8", cpu_threads=CPU_THREADS
                )
                # The first pass is ~2x slower (allocations, caches): pay it now, not on the first phrase.
                warm = np.random.default_rng(0).normal(0, 0.01, SAMPLE_RATE).astype(np.float32)
                list(self._model.transcribe(warm, language="ru", beam_size=1)[0])
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
                # 32 ms blocks: the waveform gets ~30 level updates a second
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
        self.stop()

    def _on_audio(self, data, frames, time_info, status) -> None:
        mono = data[:, 0].copy()
        self._chunks.put(mono)
        rms = float(np.sqrt(np.mean(mono * mono)))
        self.level.emit(loudness(rms))

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

    def _transcribe(self, audio: np.ndarray, offset: float, prompt: str, beam: int = 1) -> list[Word]:
        model = self._ensure_model()
        mode = LANGUAGE_MODES.get(self.config.language_mode, LANGUAGE_MODES[DEFAULT_LANGUAGE])
        started = time.monotonic()
        segments, _ = model.transcribe(
            audio,
            language=mode.whisper,
            beam_size=beam,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=prompt or None,
            # No temperature fallback: on noisy audio the default re-decodes the same chunk
            # up to 6 times, which turned a stop into a 1.5-minute wait.
            temperature=0.0,
            # A looping model can't run away: ~3x more tokens than fast speech needs.
            max_new_tokens=MAX_NEW_TOKENS,
        )
        words = [
            Word(offset + w.start, offset + w.end, w.word)
            for seg in segments
            if not _looks_hallucinated(seg)
            for w in (seg.words or [])
        ]
        took = time.monotonic() - started
        if took > SLOW_PASS_S:
            log.warning("slow pass: %.1fs for %.1fs of audio (beam %d, prompt %d chars)",
                        took, len(audio) / SAMPLE_RATE, beam, len(prompt))
        return words

    def _emit(self, words: list[Word]) -> None:
        text = join_words(words)
        if text:
            self.final.emit(text)

    @staticmethod
    def _has_speech(audio: np.ndarray) -> bool:
        return len(audio) > 0 and float(np.sqrt(np.mean(audio * audio))) >= SPEECH_RMS

    def _run(self) -> None:
        agreement = LocalAgreement()
        buffer = np.zeros(0, dtype=np.float32)
        offset = 0.0  # absolute time of buffer[0]
        pending_tail = False  # last pass left unconfirmed words: keep going even in silence
        try:
            while not self._stop.is_set():
                started = time.monotonic()
                seen = len(buffer)
                buffer = self._drain(buffer)
                # Pauses cost nothing: skip the pass if only silence arrived and nothing is pending.
                fresh_speech = self._has_speech(buffer[seen:])
                if len(buffer) >= MIN_AUDIO_S * SAMPLE_RATE and (fresh_speech or pending_tail):
                    words = self._transcribe(buffer, offset, self._prompt(agreement, offset))
                    confirmed, tail = agreement.update(words)
                    pending_tail = bool(tail)
                    self._emit(confirmed)
                    self.preview.emit(join_words(tail))
                    # Drop confirmed audio so passes stay fast.
                    cut_at = trim_point(agreement.committed, offset, len(buffer) / SAMPLE_RATE,
                                        SOFT_BUFFER_S, HARD_BUFFER_S)
                    if cut_at is not None:
                        cut = int((cut_at - offset) * SAMPLE_RATE)
                        if cut > 0:
                            buffer = buffer[cut:]
                            offset = cut_at
                self._stop.wait(max(0.0, STEP_S - (time.monotonic() - started)))

            self._close_stream()
            buffer = self._drain(buffer)
            # Last pass only if there is unconfirmed speech: on a silent tail Whisper invents text.
            tail_audio = buffer[max(0, int((agreement.committed_end - offset) * SAMPLE_RATE)):]
            if len(buffer) >= 0.2 * SAMPLE_RATE and self._has_speech(tail_audio):
                beam = FINAL_BEAM if len(buffer) / SAMPLE_RATE <= FINAL_BEAM_MAX_S else 1
                words = self._transcribe(buffer, offset, self._prompt(agreement, offset), beam=beam)
                self._emit(agreement.flush(words))
            self.preview.emit("")
        except Exception as e:
            log.exception("transcription failed")
            self.error.emit(f"Ошибка распознавания: {e}")
        finally:
            self._close_stream()
            self.stopped.emit()
