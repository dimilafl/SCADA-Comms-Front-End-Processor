"""FastAPI web server with WebSocket support for real-time SCADA diagnostics."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Any
import os

import sys
sys.path.insert(0, '/home/user/SCADA-Comms-Front-End-Processor/scada-comms-fep')

from .state import WebState
from fep.poller import EndpointRuntimeState
from fep.models import PointValue
from fep.dispatcher import Dispatcher


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_json(self, message: Dict[str, Any]) -> None:
        """
        Broadcast JSON message to all active connections.

        Automatically removes failed connections.
        """
        to_remove = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                to_remove.append(connection)
        for c in to_remove:
            self.disconnect(c)


# Global state and connection managers
web_state = WebState()
diag_manager = ConnectionManager()
points_manager = ConnectionManager()

# Create FastAPI app
app = FastAPI(title="SCADA FEP Diagnostics")

# Get the directory where this file is located
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")

# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main HTML page."""
    index_path = os.path.join(static_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/diagnostics")
async def get_diagnostics():
    """Get current diagnostics snapshot."""
    return JSONResponse(web_state.snapshot_dict())


@app.get("/api/points")
async def get_points():
    """Get recent point update history."""
    return JSONResponse(web_state.points_history_dict())


@app.websocket("/ws/diagnostics")
async def ws_diagnostics(websocket: WebSocket):
    """
    WebSocket endpoint for real-time diagnostics updates.

    Sends initial snapshot on connect, then pushes updates as they occur.
    """
    await diag_manager.connect(websocket)
    try:
        # Send initial snapshot
        await websocket.send_json({
            "type": "diagnostics_snapshot",
            "data": web_state.snapshot_dict(),
        })
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        diag_manager.disconnect(websocket)


@app.websocket("/ws/points")
async def ws_points(websocket: WebSocket):
    """
    WebSocket endpoint for real-time point updates.

    Sends initial history on connect, then pushes new updates as they arrive.
    """
    await points_manager.connect(websocket)
    try:
        # Send initial snapshot
        await websocket.send_json({
            "type": "points_snapshot",
            "data": web_state.points_history_dict(),
        })
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        points_manager.disconnect(websocket)


# Callback functions for polling engine integration

async def diagnostics_callback(
    endpoint_id: str, state: EndpointRuntimeState, dispatcher: Dispatcher
):
    """
    Callback for polling engine diagnostics updates.

    Updates web state and broadcasts to connected WebSocket clients.

    Args:
        endpoint_id: Endpoint identifier
        state: Current endpoint runtime state
        dispatcher: Dispatcher instance for queue depth
    """
    # Update web state
    web_state.update_endpoint(endpoint_id, state, queue_depth=dispatcher.queue_depth)

    # Broadcast to WebSocket clients
    await diag_manager.broadcast_json({
        "type": "diagnostics_update",
        "endpoint_id": endpoint_id,
        "data": web_state.snapshot_dict(),
    })


async def point_updates_callback(updates: list[PointValue]):
    """
    Callback for point updates from dispatcher.

    Updates web state and broadcasts to connected WebSocket clients.

    Args:
        updates: List of PointValue objects
    """
    # Add to web state and get view models
    new_views = web_state.add_point_updates(updates)

    # Broadcast to WebSocket clients
    views_dicts = []
    for v in new_views:
        views_dicts.append({
            "endpoint_id": v.endpoint_id,
            "point_name": v.point_name,
            "value": v.value,
            "quality": v.quality,
            "server_ts": v.server_ts,
            "device_ts": v.device_ts,
        })

    await points_manager.broadcast_json({
        "type": "point_updates",
        "data": views_dicts,
    })
