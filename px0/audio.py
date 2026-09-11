"""px0 audio & meeting capture: record live meetings, transcribe with Whisper,
and index into px0 brain.

Captures system audio (the remote participants via PulseAudio monitor sink)
and the local microphone (your voice) in real time via FFmpeg, mixes them,
and transcribes them locally using faster-whisper.
"""

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

DEFAULT_WHISPER_MODEL = "base.en"


class AudioCaptureError(Exception):
    """Raised when audio capture or device detection fails."""


def detect_pulse_devices() -> tuple[str, str]:
    """Detects the default PulseAudio monitor sink (output/other participants)
    and source (microphone).
    
    Returns (sink_monitor, mic_source).
    """
    if not shutil.which("ffmpeg"):
        raise AudioCaptureError("ffmpeg is not installed or not in PATH")

    result = subprocess.run(
        ["ffmpeg", "-sources", "pulse"],
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")

    sink_monitor = None
    mic_source = None

    for line in output.splitlines():
        line = line.strip()
        match = re.search(r"[* ]\s*([a-zA-Z0-9_.-]+)\s*\[(.*?)\]", line)
        if match:
            dev_name = match.group(1)
            desc = match.group(2).lower()
            if "monitor" in dev_name.lower() or "monitor" in desc:
                if not sink_monitor:
                    sink_monitor = dev_name
            elif "source" in dev_name.lower() or "mic" in desc or "input" in desc or "rdpsource" in dev_name.lower():
                if not mic_source:
                    mic_source = dev_name

    if not sink_monitor:
        sink_monitor = "RDPSink.monitor"
    if not mic_source:
        mic_source = "RDPSource"

    return sink_monitor, mic_source


@dataclass
class MeetingRecording:
    wav_path: Path
    start_time: datetime
    end_time: datetime
    duration_seconds: float


class LiveMeetingRecorder:
    """Manages an active background ffmpeg process recording both audio streams."""

    def __init__(self, sink_monitor: Optional[str] = None, mic_source: Optional[str] = None):
        detected_sink, detected_mic = detect_pulse_devices()
        self.sink_monitor = sink_monitor or detected_sink
        self.mic_source = mic_source or detected_mic
        self.process: Optional[subprocess.Popen] = None
        self.wav_path: Optional[Path] = None
        self.start_time: Optional[datetime] = None

    def start(self, output_wav: Optional[Path] = None) -> Path:
        """Starts recording in the background."""
        if self.process and self.process.poll() is None:
            raise AudioCaptureError("A recording is already running")

        if output_wav is None:
            tmp_dir = Path(tempfile.gettempdir()) / "px0_meetings"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.wav_path = tmp_dir / f"meeting_{timestamp}.wav"
        else:
            self.wav_path = Path(output_wav)
            self.wav_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "pulse", "-i", self.sink_monitor,
            "-f", "pulse", "-i", self.mic_source,
            "-filter_complex", "amix=inputs=2:duration=first:dropout_transition=2",
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(self.wav_path),
        ]

        self.start_time = datetime.now()
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.PIPE,
        )
        return self.wav_path

    def stop(self) -> MeetingRecording:
        """Stops recording gracefully and ensures audio header is cleanly written."""
        if not self.process or not self.start_time or not self.wav_path:
            raise AudioCaptureError("No active recording to stop")

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        if self.process.poll() is None:
            try:
                if self.process.stdin:
                    self.process.stdin.write(b"q\n")
                    self.process.stdin.flush()
                self.process.wait(timeout=5)
            except Exception:
                self.process.send_signal(signal.SIGINT)
                try:
                    self.process.wait(timeout=5)
                except Exception:
                    self.process.kill()

        if not self.wav_path.exists() or self.wav_path.stat().st_size == 0:
            raise AudioCaptureError(f"Recording failed or produced empty file: {self.wav_path}")

        return MeetingRecording(
            wav_path=self.wav_path,
            start_time=self.start_time,
            end_time=end_time,
            duration_seconds=duration,
        )


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


def transcribe_audio(
    wav_path: Path,
    model_size: str = DEFAULT_WHISPER_MODEL,
    on_progress: Optional[Callable[[str], None]] = None,
) -> tuple[list[TranscriptSegment], str]:
    """Transcribes a WAV file using faster-whisper.
    
    Returns (segments, detected_language).
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise AudioCaptureError(
            "faster-whisper is not installed. Install it with: pip install faster-whisper"
        ) from e

    if on_progress:
        on_progress(f"Loading Whisper model '{model_size}' (running locally)...")

    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    if on_progress:
        on_progress("Transcribing audio...")

    segments_iter, info = model.transcribe(
        str(wav_path),
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    segments: list[TranscriptSegment] = []
    for s in segments_iter:
        text = s.text.strip()
        if text:
            segments.append(TranscriptSegment(start=s.start, end=s.end, text=text))

    return segments, info.language


def format_timestamp(seconds: float) -> str:
    """Formats float seconds to HH:MM:SS or MM:SS."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def build_meeting_markdown(
    title: str,
    recording: MeetingRecording,
    segments: list[TranscriptSegment],
    tags: Optional[list[str]] = None,
) -> tuple[dict, str]:
    """Builds px0 frontmatter and body for a meeting recording."""
    today_str = recording.start_time.strftime("%Y-%m-%d")
    header = {
        "title": title,
        "date": today_str,
        "recorded_at": recording.start_time.isoformat(),
        "duration_minutes": round(recording.duration_seconds / 60, 1),
        "source": str(recording.wav_path),
        "kind": "work",
        "tags": tags or ["meeting", "audio"],
    }

    transcript_lines = []
    for s in segments:
        ts = format_timestamp(s.start)
        transcript_lines.append(f"**[{ts}]** {s.text}")

    full_transcript = "\n\n".join(transcript_lines) if transcript_lines else "_No speech detected._"

    body = f"""# {title}

**Date:** {today_str}  
**Time:** {recording.start_time.strftime('%H:%M:%S')} - {recording.end_time.strftime('%H:%M:%S')}  
**Duration:** {round(recording.duration_seconds / 60, 1)} min  

---

## Full Transcript

{full_transcript}
"""
    return header, body
