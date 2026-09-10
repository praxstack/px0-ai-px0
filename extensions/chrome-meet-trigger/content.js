// px0 Meeting Auto-Trigger Content Script
// Monitors Google Meet, Zoom, and Teams to trigger local recording daemon

const DAEMON_URL = "http://127.0.0.1:8765";

let isCallActive = false;
let meetingTitle = "";
let meetingCode = "";

// Helper to notify px0 daemon
async function notifyDaemon(action, payload = {}) {
  try {
    const url = `${DAEMON_URL}/${action}`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await response.json();
    console.log(`[px0 recorder] ${action} response:`, result);
    return result;
  } catch (err) {
    console.warn(`[px0 recorder] Could not reach px0 daemon at ${DAEMON_URL}:`, err.message);
    return null;
  }
}

// -------------------------------------------------------------
// Google Meet Detection
// -------------------------------------------------------------
function checkGoogleMeet() {
  const url = window.location.href;
  const meetCodeMatch = url.match(/meet\.google\.com\/([a-z]{3}-[a-z]{4}-[a-z]{3})/i);
  if (!meetCodeMatch) return false;

  meetingCode = meetCodeMatch[1];

  // In Google Meet:
  // "Leave call" button exists only when inside the active meeting room.
  // aria-label="Leave call" or data-tooltip="Leave call"
  const leaveButton = document.querySelector(
    'button[aria-label*="Leave call"], button[data-tooltip*="Leave call"], button[aria-label*="End call"]'
  );

  // Extract Meeting title if displayed
  const titleEl = document.querySelector('[data-meeting-title], [jsname="r4nke"], div.u6vdEc');
  if (titleEl && titleEl.textContent.trim()) {
    meetingTitle = titleEl.textContent.trim();
  } else if (!meetingTitle) {
    // Fallback to page title or meeting code
    meetingTitle = document.title.replace("- Google Meet", "").trim() || `Google Meet ${meetingCode}`;
  }

  return Boolean(leaveButton);
}

// -------------------------------------------------------------
// Zoom Web Detection
// -------------------------------------------------------------
function checkZoomWeb() {
  const url = window.location.href;
  if (!url.includes("zoom.us")) return false;

  const leaveBtn = document.querySelector('button.footer__leave-btn, button[aria-label*="Leave"]');
  if (leaveBtn) {
    meetingCode = url.match(/zoom\.us\/(?:wc|j)\/(\d+)/)?.[1] || "zoom";
    meetingTitle = document.title.replace("- Zoom", "").trim() || `Zoom Meeting ${meetingCode}`;
    return true;
  }
  return false;
}

// -------------------------------------------------------------
// Teams Web Detection
// -------------------------------------------------------------
function checkTeamsWeb() {
  const url = window.location.href;
  if (!url.includes("teams.microsoft.com")) return false;

  const hangupBtn = document.querySelector('button[aria-label*="Leave"], button[data-tid*="hangup-button"]');
  if (hangupBtn) {
    meetingTitle = document.title.replace("- Microsoft Teams", "").trim() || "Teams Meeting";
    return true;
  }
  return false;
}

function checkMeetingStatus() {
  const inMeet = checkGoogleMeet();
  const inZoom = checkZoomWeb();
  const inTeams = checkTeamsWeb();

  const nowActive = inMeet || inZoom || inTeams;

  if (nowActive && !isCallActive) {
    // Transition: Not in call -> In call!
    isCallActive = true;
    console.log(`[px0 recorder] Meeting detected! Title: "${meetingTitle}", Code: ${meetingCode}`);
    notifyDaemon("start", {
      title: meetingTitle,
      code: meetingCode,
      url: window.location.href
    });
  } else if (!nowActive && isCallActive) {
    // Transition: In call -> Left call!
    isCallActive = false;
    console.log("[px0 recorder] Meeting ended.");
    notifyDaemon("stop");
  }
}

// Check every 2 seconds
setInterval(checkMeetingStatus, 2000);

// Also watch for tab close / navigation
window.addEventListener("beforeunload", () => {
  if (isCallActive) {
    navigator.sendBeacon(`${DAEMON_URL}/stop`, JSON.stringify({ reason: "tab_closed" }));
  }
});

console.log("[px0 recorder] Meeting auto-trigger extension active for Google Meet, Zoom, and Teams.");
