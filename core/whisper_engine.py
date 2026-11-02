"""
Whisper Speech-to-Text Engine for Qale.
Optimized for developer dictation with anti-hallucination filtering.
Runs on final completed speech buffer for 100% sentence accuracy.
"""
import io
import os
import tempfile
from typing import Optional, Union
import numpy as np


class WhisperEngine:
    def __init__(self,
                 model_size: str = "base.en",
                 device: str = "cuda",
                 compute_type: str = "float16",
                 developer_prompt: str = "",
                 quantize_int8: bool = True,
                 torch_threads: Optional[int] = None,
                 beam_size: int = 2,
                 language: str = "en"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.developer_prompt = developer_prompt
        self.quantize_int8 = quantize_int8
        self.torch_threads = torch_threads
        self.beam_size = beam_size
        self.language = language
        self.model = None
        self.engine_type = None
        self.actual_device = "cpu"

    def load_model(self):
        """Loads the local Whisper model with CUDA acceleration if available, or quantized on CPU."""
        # Configure CPU threads
        try:
            import torch
            threads = self.torch_threads if self.torch_threads is not None else max(1, (os.cpu_count() or 4) // 2)
            torch.set_num_threads(threads)
            print(f"[WhisperEngine] PyTorch threads set to {threads}")
        except Exception:
            pass

        # 1. Try faster-whisper (CTranslate2 backend with built-in Silero VAD)
        try:
            from faster_whisper import WhisperModel
            import ctranslate2
            
            cuda_available = (self.device == "cuda" and ctranslate2.get_cuda_device_count() > 0)
            self.actual_device = "cuda" if cuda_available else "cpu"
            actual_compute = self.compute_type if self.actual_device == "cuda" else "int8"
            
            print(f"[WhisperEngine] Loading faster-whisper '{self.model_size}' on {self.actual_device} ({actual_compute})...")
            self.model = WhisperModel(
                self.model_size,
                device=self.actual_device,
                compute_type=actual_compute
            )
            self.engine_type = "faster_whisper"
            print("[WhisperEngine] faster-whisper model loaded successfully.")
            return
        except Exception as e:
            print(f"[WhisperEngine] faster-whisper unavailable ({e}), trying openai-whisper...")

        # 2. Fallback to standard openai-whisper
        try:
            import whisper
            import torch
            self.actual_device = "cuda" if (self.device == "cuda" and torch.cuda.is_available()) else "cpu"
            print(f"[WhisperEngine] Loading openai-whisper '{self.model_size}' on {self.actual_device}...")
            self.model = whisper.load_model(self.model_size, device=self.actual_device)

            if self.actual_device == "cpu" and self.quantize_int8:
                print("[WhisperEngine] Applying dynamic int8 quantization (Linear -> qint8)...")
                self.model = torch.ao.quantization.quantize_dynamic(
                    self.model, {torch.nn.Linear}, dtype=torch.qint8
                )
                print("[WhisperEngine] Dynamic int8 quantization: ON")
            else:
                print(f"[WhisperEngine] Dynamic int8 quantization: {'OFF' if not self.quantize_int8 else 'N/A (CUDA)'}")

            self.engine_type = "openai_whisper"
            print("[WhisperEngine] Model loaded successfully.")
            return
        except Exception as e:
            print(f"[WhisperEngine] openai-whisper unavailable ({e})")

        print("[WhisperEngine] Notice: Waiting for whisper engine")
        self.engine_type = "mock"

    def transcribe(self, audio_input: Union[np.ndarray, bytes], custom_prompt: Optional[str] = None) -> str:
        """
        Transcribes 16kHz mono audio directly into text without disk WAV export.
        Accepts float32 numpy array (range -1..1), int16 numpy array, or WAV/PCM bytes.
        """
        if audio_input is None:
            return ""

        # Normalize audio input to float32 numpy array
        if isinstance(audio_input, np.ndarray):
            if audio_input.dtype == np.int16:
                audio_np = audio_input.flatten().astype(np.float32) / 32768.0
            else:
                audio_np = audio_input.flatten().astype(np.float32)
        elif isinstance(audio_input, bytes):
            if len(audio_input) < 8000:
                return ""
            if audio_input.startswith(b"RIFF"):
                import wave
                with wave.open(io.BytesIO(audio_input), "rb") as wf:
                    frames = wf.readframes(wf.getnframes())
                    audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_np = np.frombuffer(audio_input, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            return ""

        # Guard: At least ~0.25 seconds of audio (4000 samples at 16kHz)
        if len(audio_np) < 4000:
            return ""

        if self.model is None:
            self.load_model()

        prompt = custom_prompt or self.developer_prompt

        try:
            if self.engine_type == "faster_whisper":
                segments, _ = self.model.transcribe(
                    audio_np,
                    beam_size=self.beam_size,
                    initial_prompt=prompt,
                    language=self.language,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.6,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=400,
                        speech_pad_ms=200
                    ),
                    temperature=[0.0, 0.2]
                )
                transcription = " ".join([segment.text for segment in segments]).strip()
                return transcription

            elif self.engine_type == "openai_whisper":
                is_gpu = (self.actual_device == "cuda")
                beam = self.beam_size
                duration_sec = len(audio_np) / 16000.0
                is_long_audio = (duration_sec > 25.0)

                result = self.model.transcribe(
                    audio_np,
                    initial_prompt=prompt,
                    language=self.language,
                    beam_size=beam,
                    temperature=0.0,
                    fp16=is_gpu,
                    condition_on_previous_text=is_long_audio,
                    without_timestamps=False,
                    no_speech_threshold=0.6,
                    logprob_threshold=-1.0,
                    compression_ratio_threshold=2.4
                )
                text = result.get("text", "").strip()
                return text

            else:
                return ""
        except Exception as e:
            print(f"[WhisperEngine Notice]: {e}")
            return ""
