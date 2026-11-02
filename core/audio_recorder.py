"""
Audio Recorder for Qale.
Records microphone audio and applies highpass filtering, optional spectral gating,
pre-emphasis, dynamic range normalization, and conservative silence trimming.
Directly produces 16kHz float32 NumPy arrays for zero-copy Whisper inference.
"""
import io
import threading
import wave
import winsound
from typing import List, Dict, Optional
import numpy as np

SR = 16000

# Try importing scipy; fallback to pure NumPy implementations if scipy is unavailable
try:
    from scipy.signal import butter, sosfilt, stft, istft
    _HP = butter(4, 80, btype="highpass", fs=SR, output="sos")
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False
    _HP = np.array([
        [0.98787861, -1.97575721,  0.98787861,  1.0, -1.97526963, 0.97624479],
        [0.97155888, -1.94311775,  0.97155888,  1.0, -1.94263823, 0.94359728]
    ], dtype=np.float64)

    def sosfilt(sos, x):
        """Pure NumPy second-order sections (biquad) IIR filter."""
        y = x.astype(np.float64)
        for s in sos:
            b0, b1, b2, _, a1, a2 = s
            out = np.empty_like(y)
            w1, w2 = 0.0, 0.0
            for i in range(len(y)):
                w0 = y[i] - a1 * w1 - a2 * w2
                out[i] = b0 * w0 + b1 * w1 + b2 * w2
                w2 = w1
                w1 = w0
            y = out
        return y.astype(x.dtype)

    def stft(x, fs=SR, nperseg=512, noverlap=384):
        """Pure NumPy STFT with Hann window."""
        hop = nperseg - noverlap
        window = np.hanning(nperseg).astype(np.float32)
        n_frames = max(1, (len(x) - noverlap) // hop)
        padded_len = n_frames * hop + noverlap
        x_pad = np.pad(x, (0, max(0, padded_len - len(x))))
        frames = np.lib.stride_tricks.sliding_window_view(x_pad[:padded_len], nperseg)[::hop]
        Z = np.fft.rfft(frames * window, axis=-1).T
        f = np.fft.rfftfreq(nperseg, 1.0 / fs)
        t = np.arange(n_frames) * (hop / fs)
        return f, t, Z

    def istft(Z, fs=SR, nperseg=512, noverlap=384):
        """Pure NumPy ISTFT with overlap-add."""
        hop = nperseg - noverlap
        window = np.hanning(nperseg).astype(np.float32)
        n_frames = Z.shape[1]
        frames = np.fft.irfft(Z.T, axis=-1) * window
        out_len = (n_frames - 1) * hop + nperseg
        out = np.zeros(out_len, dtype=np.float32)
        win_norm = np.zeros(out_len, dtype=np.float32)
        for i in range(n_frames):
            start = i * hop
            out[start : start + nperseg] += frames[i]
            win_norm[start : start + nperseg] += window ** 2
        win_norm[win_norm < 1e-6] = 1.0
        return np.arange(out_len) / fs, out / win_norm


def spectral_gate(x, noise_ms=200, strength=1.0, floor=0.15):
    """Frequency-domain spectral subtraction for stationary background noise."""
    f, t, Z = stft(x, fs=SR, nperseg=512, noverlap=384)
    mag, phase = np.abs(Z), np.angle(Z)
    n_frames = max(1, int(noise_ms / 1000 * SR / 128))
    noise = mag[:, :n_frames].mean(axis=1, keepdims=True)
    clean = np.maximum(mag - strength * noise, floor * mag)
    _, y = istft(clean * np.exp(1j * phase), fs=SR, nperseg=512, noverlap=384)
    return y[:len(x)].astype(np.float32)


def prep_audio(pcm16, pre_emph=0.0, gate=False, highpass=True):
    """
    Standardizes 16kHz audio for Whisper: highpass, optional spectral gate,
    optional pre-emphasis, 99.5-percentile peak normalization, and 300ms padding.
    """
    x = pcm16.astype(np.float32) / 32768.0
    if highpass:
        x = sosfilt(_HP, x).astype(np.float32)
    if gate:
        x = spectral_gate(x)
    if pre_emph > 0.0:
        x = np.append(x[0], x[1:] - pre_emph * x[:-1])
    peak = float(np.percentile(np.abs(x), 99.5)) + 1e-9
    x = np.clip(x * (0.7 / peak), -1.0, 1.0)
    pad = np.zeros(int(0.3 * SR), np.float32)
    return np.concatenate([pad, x, pad])


class AudioRecorder:
    def __init__(self,
                 sample_rate: int = 16000,
                 channels: int = 1,
                 highpass: bool = True,
                 spectral_gate: bool = False,
                 pre_emphasis: float = 0.0):
        self.sample_rate = sample_rate
        self.channels = channels
        self.highpass = highpass
        self.spectral_gate = spectral_gate
        self.pre_emphasis = pre_emphasis
        self.is_recording = False

        self._frames = []
        self._stream = None
        self._lock = threading.Lock()
        self._current_rms = 0.0
        self._recent_chunk = np.zeros(1024, dtype=np.float32)
        self.last_audio_float = None

    def play_start_sound(self):
        try:
            winsound.Beep(1200, 70)
        except Exception:
            pass

    def play_stop_sound(self):
        try:
            winsound.Beep(800, 70)
        except Exception:
            pass

    def start(self, device_index: Optional[int] = None):
        """Starts capturing audio continuously."""
        import sounddevice as sd
        
        with self._lock:
            self._frames = []
            self.is_recording = True
            self._current_rms = 0.0
            self._recent_chunk = np.zeros(1024, dtype=np.float32)
            self.last_audio_float = None

        def callback(indata, frames, time_info, status):
            if self.is_recording:
                with self._lock:
                    self._frames.append(indata.copy())
                    self._recent_chunk = indata[-1024:, 0].astype(np.float32) / 32768.0

                raw = indata.astype(np.float32)
                rms = float(np.sqrt(np.mean(raw ** 2))) / 32768.0
                norm_vol = min(1.0, rms * 8.5)
                self._current_rms = 0.35 * self._current_rms + 0.65 * norm_vol

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            device=device_index,
            callback=callback
        )
        self._stream.start()

    def get_audio_levels(self, num_bars: int = 28) -> List[float]:
        """Returns instantaneous energy levels across sub-bands for the wave visualizer."""
        with self._lock:
            chunk = self._recent_chunk.copy()
            overall_rms = self._current_rms

        if len(chunk) < num_bars:
            return [overall_rms] * num_bars

        step = len(chunk) // num_bars
        levels = []
        for i in range(num_bars):
            sub = chunk[i * step : (i + 1) * step]
            sub_rms = float(np.sqrt(np.mean(sub ** 2)))
            val = min(1.0, sub_rms * 9.5 * 0.75 + overall_rms * 0.25)
            levels.append(val)
        return levels

    def stop(self) -> Optional[np.ndarray]:
        """
        Stops capturing and returns preprocessed float32 NumPy array ready for Whisper.
        Uses conservative silence trimming and prep_audio conditioning.
        """
        self.is_recording = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            if not self._frames:
                return None
            audio_data = np.concatenate(self._frames, axis=0).flatten()
            self._frames = []

        # If audio is shorter than 0.25s (4000 samples at 16kHz), discard
        if len(audio_data) < 4000:
            return None

        # Conservative silence trimming (preserves faint initial consonants + 300ms pad)
        trimmed = self._trim_silence_conservative(audio_data, pad_ms=300)
        if len(trimmed) < 4000:
            trimmed = audio_data

        # Condition audio (highpass, optional gate/pre-emphasis, peak norm, padding)
        audio_float = prep_audio(
            trimmed,
            pre_emph=self.pre_emphasis,
            gate=self.spectral_gate,
            highpass=self.highpass
        )

        self.last_audio_float = audio_float
        return audio_float

    def _trim_silence_conservative(self, audio_data: np.ndarray, pad_ms: int = 300) -> np.ndarray:
        """
        Conservatively trims leading silence so initial speech is captured cleanly,
        while preserving all trailing audio to ensure ending words are never cut off.
        """
        if len(audio_data) == 0:
            return audio_data

        samples = audio_data.flatten().astype(np.float32) / 32768.0
        frame_len = int(self.sample_rate * 0.03)  # 30ms chunks
        if len(samples) < frame_len:
            return audio_data

        num_frames = len(samples) // frame_len
        energies = [
            float(np.sqrt(np.mean(samples[i * frame_len : (i + 1) * frame_len] ** 2)))
            for i in range(num_frames)
        ]

        if not energies:
            return audio_data

        # Conservative threshold: captures quiet fricatives/plosives
        noise_floor = float(np.percentile(energies, 15)) if len(energies) > 5 else 0.005
        active_thresh = max(0.006, noise_floor * 1.5)

        active_indices = [i for i, e in enumerate(energies) if e > active_thresh]
        if not active_indices:
            return audio_data

        pad_frames = max(1, int((pad_ms / 1000.0) * self.sample_rate / frame_len))
        start_frame = max(0, active_indices[0] - pad_frames)
        start_idx = start_frame * frame_len

        # Crucial: NEVER truncate trailing audio!
        # The user explicitly stops recording when finished speaking. Slicing the tail
        # risks amputating trailing words/syllables when voice drops at the end of long sentences.
        end_idx = len(audio_data)
        return audio_data[start_idx:end_idx]

    def to_wav(self, audio_data: Optional[np.ndarray] = None) -> bytes:
        """Converts float32 or int16 NumPy array to standard 16kHz mono WAV bytes."""
        arr = audio_data if audio_data is not None else self.last_audio_float
        if arr is None or len(arr) == 0:
            return b""
        if arr.dtype != np.int16:
            arr_int16 = np.clip(arr * 32767.0, -32768, 32767).astype(np.int16)
        else:
            arr_int16 = arr
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(arr_int16.tobytes())
        return wav_io.getvalue()

    @staticmethod
    def get_input_devices() -> List[Dict]:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = []
            for idx, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0:
                    input_devices.append({
                        "index": idx,
                        "name": dev.get("name", f"Microphone {idx}"),
                        "channels": dev.get("max_input_channels")
                    })
            return input_devices
        except Exception:
            return []
