"""Web state manager for SCADA FEP diagnostics and point updates."""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List

import sys
sys.path.insert(0, '/home/user/SCADA-Comms-Front-End-Processor/scada-comms-fep')

from fep.poller import EndpointRuntimeState
from fep.models import PointValue


@dataclass
class EndpointView:
    """View model for endpoint diagnostics."""
    endpoint_id: str
    health: str
    last_poll_started: str | None
    last_rtt_ms: float | None
    consecutive_failures: int
    last_fault: str | None
    queue_depth: int


@dataclass
class DiagnosticsSnapshot:
    """Snapshot of all endpoint diagnostics."""
    queue_depth: int
    endpoints: Dict[str, EndpointView] = field(default_factory=dict)


@dataclass
class PointUpdateView:
    """View model for a single point update."""
    endpoint_id: str
    point_name: str
    value: float | bool
    quality: str
    server_ts: str
    device_ts: str | None


class WebState:
    """
    Shared state for web UI.

    Maintains current diagnostics snapshot and recent point update history
    for serving to web clients via REST and WebSocket.
    """

    def __init__(self, max_points_history: int = 100):
        self._snapshot = DiagnosticsSnapshot(queue_depth=0)
        self._point_history: List[PointUpdateView] = []
        self._max_points_history = max_points_history

    def update_endpoint(
        self,
        endpoint_id: str,
        state: EndpointRuntimeState,
        queue_depth: int,
    ) -> None:
        """
        Update endpoint state in the snapshot.

        Args:
            endpoint_id: Endpoint identifier
            state: Current runtime state from polling engine
            queue_depth: Current dispatcher queue depth
        """
        lp = (
            state.last_poll_started.isoformat()
            if state.last_poll_started
            else None
        )
        ev = EndpointView(
            endpoint_id=endpoint_id,
            health=state.health.value,
            last_poll_started=lp,
            last_rtt_ms=state.last_rtt_ms,
            consecutive_failures=state.consecutive_failures,
            last_fault=state.last_fault,
            queue_depth=queue_depth,
        )
        self._snapshot.endpoints[endpoint_id] = ev
        self._snapshot.queue_depth = queue_depth

    def add_point_updates(self, updates: list[PointValue]) -> list[PointUpdateView]:
        """
        Add point updates to history.

        Args:
            updates: List of PointValue objects

        Returns:
            List of PointUpdateView objects that were added
        """
        views: list[PointUpdateView] = []
        for pv in updates:
            v = PointUpdateView(
                endpoint_id=pv.definition.address.endpoint_id,
                point_name=pv.definition.address.point_name,
                value=pv.value,
                quality=pv.quality.value,
                server_ts=pv.server_ts.isoformat(),
                device_ts=pv.device_ts.isoformat() if pv.device_ts else None,
            )
            self._point_history.append(v)
            views.append(v)

        # Trim to max history
        if len(self._point_history) > self._max_points_history:
            self._point_history = self._point_history[-self._max_points_history :]

        return views

    def snapshot_dict(self) -> dict:
        """Get current diagnostics snapshot as dict for JSON serialization."""
        return {
            "queue_depth": self._snapshot.queue_depth,
            "endpoints": {
                eid: asdict(ev) for eid, ev in self._snapshot.endpoints.items()
            },
        }

    def points_history_dict(self) -> list[dict]:
        """Get point update history as list of dicts for JSON serialization."""
        return [asdict(v) for v in self._point_history]
