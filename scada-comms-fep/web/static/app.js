// SCADA FEP Diagnostics - WebSocket Client

const endpointBody = document.getElementById("endpoint-body");
const pointsBody = document.getElementById("points-body");
const queueDepthSpan = document.getElementById("queue-depth");
const connectionStatus = document.getElementById("connection-status");
const connectionText = document.getElementById("connection-text");

let diagWs = null;
let pointsWs = null;

/**
 * Update connection status indicator
 */
function updateConnectionStatus(connected) {
  if (connected) {
    connectionStatus.className = "status-connected";
    connectionText.textContent = "Connected";
  } else {
    connectionStatus.className = "status-disconnected";
    connectionText.textContent = "Disconnected";
  }
}

/**
 * Format timestamp for display
 */
function formatTimestamp(isoString) {
  if (!isoString) return "-";
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString() + "." + date.getMilliseconds().toString().padStart(3, "0");
  } catch (e) {
    return isoString;
  }
}

/**
 * Render diagnostics snapshot
 */
function renderDiagnostics(snapshot) {
  queueDepthSpan.textContent = snapshot.queue_depth ?? 0;

  const endpoints = snapshot.endpoints || {};
  const endpointIds = Object.keys(endpoints).sort();

  if (endpointIds.length === 0) {
    endpointBody.innerHTML = '<tr><td colspan="7" class="no-data">No endpoints configured</td></tr>';
    return;
  }

  endpointBody.innerHTML = "";

  endpointIds.forEach((id) => {
    const ep = endpoints[id];
    const tr = document.createElement("tr");

    const healthClass = "health-" + (ep.health || "UNKNOWN");

    tr.innerHTML = `
      <td>${ep.endpoint_id}</td>
      <td class="${healthClass}">${ep.health}</td>
      <td>${formatTimestamp(ep.last_poll_started)}</td>
      <td>${ep.last_rtt_ms != null ? ep.last_rtt_ms.toFixed(1) : "-"}</td>
      <td>${ep.consecutive_failures}</td>
      <td>${ep.queue_depth}</td>
      <td>${ep.last_fault || ""}</td>
    `;
    endpointBody.appendChild(tr);
  });
}

/**
 * Format point value for display
 */
function formatValue(value) {
  if (typeof value === "boolean") {
    return value ? "TRUE" : "FALSE";
  }
  if (typeof value === "number") {
    return value.toFixed(2);
  }
  return String(value);
}

/**
 * Append point update rows to table
 */
function appendPointRows(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return;
  }

  // Remove "no data" row if present
  const noDataRow = pointsBody.querySelector(".no-data");
  if (noDataRow) {
    noDataRow.parentElement.remove();
  }

  rows.forEach((p) => {
    const tr = document.createElement("tr");
    const qualityClass = "quality-" + (p.quality || "UNKNOWN");

    tr.innerHTML = `
      <td>${p.endpoint_id}</td>
      <td>${p.point_name}</td>
      <td>${formatValue(p.value)}</td>
      <td class="${qualityClass}">${p.quality}</td>
      <td>${formatTimestamp(p.server_ts)}</td>
      <td>${formatTimestamp(p.device_ts)}</td>
    `;

    // Add to top of table
    pointsBody.insertBefore(tr, pointsBody.firstChild);

    // Trim to max 100 rows
    while (pointsBody.rows.length > 100) {
      pointsBody.deleteRow(pointsBody.rows.length - 1);
    }
  });
}

/**
 * Setup diagnostics WebSocket
 */
function setupDiagnosticsWS() {
  if (diagWs) {
    diagWs.close();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/diagnostics`;

  console.log("Connecting to diagnostics WebSocket:", wsUrl);
  diagWs = new WebSocket(wsUrl);

  diagWs.onopen = () => {
    console.log("Diagnostics WebSocket connected");
    updateConnectionStatus(true);
  };

  diagWs.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      console.log("Diagnostics message:", msg.type);

      if (msg.type === "diagnostics_snapshot" || msg.type === "diagnostics_update") {
        renderDiagnostics(msg.data);
      }
    } catch (e) {
      console.error("Error processing diagnostics message:", e);
    }
  };

  diagWs.onerror = (error) => {
    console.error("Diagnostics WebSocket error:", error);
  };

  diagWs.onclose = () => {
    console.log("Diagnostics WebSocket closed, reconnecting...");
    updateConnectionStatus(false);
    setTimeout(setupDiagnosticsWS, 2000);
  };
}

/**
 * Setup points WebSocket
 */
function setupPointsWS() {
  if (pointsWs) {
    pointsWs.close();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/points`;

  console.log("Connecting to points WebSocket:", wsUrl);
  pointsWs = new WebSocket(wsUrl);

  pointsWs.onopen = () => {
    console.log("Points WebSocket connected");
  };

  pointsWs.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      console.log("Points message:", msg.type, "count:", msg.data?.length || 0);

      if (msg.type === "points_snapshot") {
        // Initial snapshot - reverse to show newest first
        const reversed = [...(msg.data || [])].reverse();
        appendPointRows(reversed);
      } else if (msg.type === "point_updates") {
        appendPointRows(msg.data || []);
      }
    } catch (e) {
      console.error("Error processing points message:", e);
    }
  };

  pointsWs.onerror = (error) => {
    console.error("Points WebSocket error:", error);
  };

  pointsWs.onclose = () => {
    console.log("Points WebSocket closed, reconnecting...");
    setTimeout(setupPointsWS, 2000);
  };
}

/**
 * Initialize on page load
 */
window.addEventListener("load", () => {
  console.log("SCADA FEP Diagnostics UI initialized");
  setupDiagnosticsWS();
  setupPointsWS();
});

/**
 * Cleanup on page unload
 */
window.addEventListener("beforeunload", () => {
  if (diagWs) diagWs.close();
  if (pointsWs) pointsWs.close();
});
