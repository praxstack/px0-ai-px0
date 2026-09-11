"""px0 meeting daemon & HTTP server: listens for browser / extension webhook triggers
to start and stop meeting recordings, saving audio to ~/.px0/meetings/ and indexing
into px0 brain.
"""

import json
import logging
import re
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from px0 import audio as audio_mod, brain as brain_mod, paths, retrieval

logger = logging.getLogger("px0.meeting_server")


class MeetingManager:
    """Singleton manager tracking the active recording session."""

    def __init__(self, home: Optional[Path] = None, config: Optional[dict] = None):
        self.home = home or paths.store_home()
        self.config = config or {}
        self.recorder: Optional[audio_mod.LiveMeetingRecorder] = None
        self.current_title: Optional[str] = None
        self.current_code: Optional[str] = None
        self.lock = threading.RLock()
        self.target_folder = "work"
        self.model_size = "base.en"

    def is_recording(self) -> bool:
        with self.lock:
            return self.recorder is not None and self.recorder.process is not None and self.recorder.process.poll() is None

    def status(self) -> dict:
        with self.lock:
            if not self.is_recording():
                return {
                    "recording": False,
                    "title": None,
                    "started_at": None,
                    "duration_seconds": 0,
                }
            started = self.recorder.start_time
            duration = (datetime.now() - started).total_seconds() if started else 0
            return {
                "recording": True,
                "title": self.current_title,
                "code": self.current_code,
                "started_at": started.isoformat() if started else None,
                "duration_seconds": round(duration, 1),
                "wav_path": str(self.recorder.wav_path),
            }

    def start(self, title: Optional[str] = None, code: Optional[str] = None) -> dict:
        with self.lock:
            if self.is_recording():
                return {
                    "ok": True,
                    "status": "already_recording",
                    "title": self.current_title,
                }

            sink, mic = audio_mod.detect_pulse_devices()
            self.recorder = audio_mod.LiveMeetingRecorder(sink_monitor=sink, mic_source=mic)

            meetings_folder = paths.meetings_dir(self.home)
            meetings_folder.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_title = re.sub(r"[^a-zA-Z0-9_\-]+", "_", (title or "Meeting").strip())[:40]
            wav_file = meetings_folder / f"{timestamp}_{clean_title}.wav"

            self.current_title = title or f"Meeting {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            self.current_code = code

            self.recorder.start(output_wav=wav_file)
            logger.info("Started meeting recording: %s -> %s", self.current_title, wav_file)
            return {
                "ok": True,
                "status": "started",
                "title": self.current_title,
                "file": str(wav_file),
            }

    def stop(self) -> dict:
        with self.lock:
            if not self.is_recording():
                return {"ok": False, "error": "No active recording to stop"}

            try:
                recording = self.recorder.stop()
            except Exception as e:
                logger.error("Error stopping recording: %s", e)
                self.recorder = None
                return {"ok": False, "error": str(e)}

            title = self.current_title or "Meeting"
            code = self.current_code
            self.recorder = None
            self.current_title = None
            self.current_code = None

        # Process transcription & indexing in background thread so the HTTP response returns immediately
        threading.Thread(
            target=self._process_recording,
            args=(title, recording, code),
            daemon=True,
        ).start()

        return {
            "ok": True,
            "status": "stopped",
            "file": str(recording.wav_path),
            "duration_seconds": round(recording.duration_seconds, 1),
            "message": "Processing transcript and indexing into brain...",
        }

    def _process_recording(
        self, title: str, recording: audio_mod.MeetingRecording, code: Optional[str] = None
    ) -> None:
        try:
            logger.info("Transcribing recording: %s", recording.wav_path)
            segments, lang = audio_mod.transcribe_audio(recording.wav_path, model_size=self.model_size)
            tags = ["meeting", "audio"]
            if code:
                tags.append(f"meeting-code:{code}")

            header, body = audio_mod.build_meeting_markdown(
                title=title,
                recording=recording,
                segments=segments,
                tags=tags,
            )

            date_str = recording.start_time.strftime("%Y%m%d-%H%M")
            slug = brain_mod._slug_from_source(f"meeting-{date_str}-{title}")
            dest = (
                brain_mod.brain_path(self.home, self.config)
                / brain_mod.resolve_folder(self.home, self.config, self.target_folder)
                / f"{slug}.md"
            )

            brain_mod.write_file(dest, header, body)
            logger.info("Meeting note saved: %s", dest)

            retrieval.reindex(self.home, self.config)
            logger.info("Brain reindexed successfully.")
        except Exception as e:
            logger.exception("Failed to process meeting recording: %s", e)


def create_handler(manager: MeetingManager):
    class MeetingRequestHandler(BaseHTTPRequestHandler):
        def _send_json(self, status_code: int, data: dict):
            body = json.dumps(data).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/status":
                self._send_json(200, manager.status())
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            query_params = parse_qs(parsed.query)

            # Also parse body if provided
            content_length = int(self.headers.get("Content-Length", 0))
            body_json = {}
            if content_length > 0:
                try:
                    body_bytes = self.rfile.read(content_length)
                    body_json = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    pass

            title = (
                body_json.get("title")
                or query_params.get("title", [None])[0]
            )
            code = (
                body_json.get("code")
                or query_params.get("code", [None])[0]
            )

            if parsed.path == "/start":
                resp = manager.start(title=title, code=code)
                self._send_json(200, resp)
            elif parsed.path == "/stop":
                resp = manager.stop()
                status_code = 200 if resp.get("ok") else 400
                self._send_json(status_code, resp)
            else:
                self._send_json(404, {"error": "not found"})

        def log_message(self, format, *args):
            logger.debug("%s - - [%s] %s\n", self.client_address[0], self.log_date_time_string(), format % args)

    return MeetingRequestHandler


def run_server(
    home: Optional[Path] = None,
    config: Optional[dict] = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    """Runs the meeting listener HTTP server."""
    manager = MeetingManager(home=home, config=config)
    handler = create_handler(manager)
    server = ThreadingHTTPServer((host, port), handler)
    return server
