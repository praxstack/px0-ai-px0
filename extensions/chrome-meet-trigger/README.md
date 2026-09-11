# px0 Meeting Auto-Recorder (Chrome Extension)

This extension automatically starts and stops recording when you join and leave Google Meet, Zoom Web, or Microsoft Teams calls. The audio is recorded locally, saved to `~/.px0/meetings/`, and transcribed into `px0 brain`.

---

## Prerequisites

1. **px0** installed with `faster-whisper` and `ffmpeg`.
2. PulseAudio / WSLg audio enabled.

---

## 1. Start the px0 Meeting Daemon

Before joining a meeting, start the background daemon:

```bash
px0 brain listen
```

Options:
- `--port 8765`: Port to listen on (default `8765`).
- `--model base.en`: Whisper model size (`tiny.en`, `base.en`, `small.en`, `medium.en`, etc.).

*(Tip: You can keep this running in a tmux/screen session or set it up as a systemd user service).*

---

## 2. Install the Extension in Chrome

1. Open Google Chrome.
2. In the URL bar, go to:
   ```text
   chrome://extensions/
   ```
3. In the top-right corner, turn on **Developer mode**.
4. In the top-left corner, click **Load unpacked**.
5. Select this folder:
   - **From Windows**: `\\wsl$\Ubuntu\home\arpit\workspace\px0\px0\extensions\chrome-meet-trigger`
   - **From Linux**: `/home/arpit/workspace/px0/px0/extensions/chrome-meet-trigger`

---

## 3. How It Works

1. Open any **Google Meet** room (e.g. `meet.google.com/xyz-abc-def`).
2. When you click **Join now**, the extension detects call entry, extracts the meeting title, and calls the px0 daemon.
3. Dual-stream recording begins automatically (speakers loopback + microphone). The raw `.wav` is saved in:
   ```text
   ~/.px0/meetings/YYYYMMDD_HHMMSS_<Meeting_Title>.wav
   ```
4. When you click **Leave call** (or close the tab), the extension notifies the daemon to stop.
5. px0 transcribes the audio with Whisper, generates a Markdown note in `~/.px0/brain/work/`, and updates the brain search index.

---

## 4. Querying Your Meeting Notes

Once the meeting finishes, you can query decisions, action items, or discussion points directly from your terminal:

```bash
px0 brain ask "What action items were decided in today's sprint sync?"
```

or search across transcripts:

```bash
px0 brain search "database migration"
```
