const DAEMON_URL = "http://127.0.0.1:8765";

async function checkStatus() {
  const daemonStatus = document.getElementById("daemon-status");
  const recStatus = document.getElementById("rec-status");
  const indicator = document.getElementById("indicator");
  const offlineHelp = document.getElementById("offline-help");
  const titleRow = document.getElementById("title-row");
  const meetingTitle = document.getElementById("meeting-title");

  try {
    const res = await fetch(`${DAEMON_URL}/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    daemonStatus.textContent = "Connected";
    daemonStatus.style.color = "#059669";
    offlineHelp.style.display = "none";

    if (data.recording) {
      recStatus.textContent = `Active (${Math.floor(data.duration_seconds)}s)`;
      recStatus.style.color = "#dc2626";
      indicator.className = "badge active";
      if (data.title) {
        titleRow.style.display = "flex";
        meetingTitle.textContent = data.title;
      }
    } else {
      recStatus.textContent = "Idle";
      recStatus.style.color = "#4b5563";
      indicator.className = "badge ready";
      titleRow.style.display = "none";
    }
  } catch (e) {
    daemonStatus.textContent = "Offline";
    daemonStatus.style.color = "#dc2626";
    recStatus.textContent = "-";
    indicator.className = "badge";
    offlineHelp.style.display = "block";
    titleRow.style.display = "none";
  }
}

checkStatus();
setInterval(checkStatus, 1500);
