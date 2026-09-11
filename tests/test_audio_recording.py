import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from px0 import audio, brain


def test_detect_pulse_devices():
    sink, mic = audio.detect_pulse_devices()
    assert sink is not None
    assert mic is not None


def test_format_timestamp():
    assert audio.format_timestamp(65) == "01:05"
    assert audio.format_timestamp(3665) == "01:01:05"
    assert audio.format_timestamp(0) == "00:00"


def test_build_meeting_markdown():
    from datetime import datetime
    t0 = datetime(2026, 9, 10, 10, 0, 0)
    t1 = datetime(2026, 9, 10, 10, 15, 0)
    recording = audio.MeetingRecording(
        wav_path=Path("/tmp/test.wav"),
        start_time=t0,
        end_time=t1,
        duration_seconds=900,
    )
    segments = [
        audio.TranscriptSegment(0.0, 5.0, "Hello team, welcome to the meeting."),
        audio.TranscriptSegment(5.5, 12.0, "We decided to deploy the new indexing pipeline."),
    ]
    header, body = audio.build_meeting_markdown("Sprint Sync", recording, segments)
    assert header["title"] == "Sprint Sync"
    assert header["date"] == "2026-09-10"
    assert header["duration_minutes"] == 15.0
    assert header["kind"] == "work"
    assert "**[00:00]** Hello team" in body
    assert "**[00:05]** We decided to deploy" in body


def test_audio_suffix_supported():
    for ext in [".wav", ".mp3", ".m4a", ".ogg", ".flac"]:
        assert ext in brain._SUFFIX_KINDS
        assert brain._SUFFIX_KINDS[ext] == ("audio", "work")


def test_meeting_manager_lifecycle():
    from px0 import meeting_server
    manager = meeting_server.MeetingManager()
    assert manager.is_recording() is False
    status = manager.status()
    assert status["recording"] is False

