"""
Core polling engine for SCADA FEP.

Manages scheduled polls, timeouts, retries, quality classification,
and dispatching of point updates.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable, Dict, List, Optional

from .models import PointDef, PointValue, QualityFlag
from .protocol import encode_poll_request, decode_poll_response
from .quality import QualityModel, CommsState
from .timebase import now_utc


@dataclass
class EndpointPollConfig:
    """Configuration for polling an endpoint."""
    endpoint_id: str
    host: str
    port: int
    poll_interval_sec: float
    timeout_sec: float = 1.0
    max_retries: int = 3
    points: List[PointDef] = field(default_factory=list)
    priority: int = 1  # For priority-based scheduling (future use)


@dataclass
class EndpointRuntimeState:
    """Runtime state for an endpoint."""
    last_success: Optional[datetime] = None
    last_rtt_ms: Optional[float] = None
    consecutive_failures: int = 0
    last_fault: Optional[str] = None
    last_poll_started: Optional[datetime] = None
    queue_depth: int = 0  # Updated by dispatcher
    health: CommsState = CommsState.COMM_LOSS


# Type aliases for callbacks
PointUpdateHandler = Callable[[List[PointValue]], Awaitable[None]]
DiagnosticsUpdateHandler = Callable[[str, EndpointRuntimeState], Awaitable[None]]


class PollingEngine:
    """
    Main polling engine for the FEP.

    Manages concurrent polling loops for multiple endpoints, handles retries,
    classifies quality, and dispatches updates.
    """

    def __init__(
        self,
        quality_model: Optional[QualityModel] = None,
        on_point_updates: Optional[PointUpdateHandler] = None,
        on_diagnostics: Optional[DiagnosticsUpdateHandler] = None,
    ) -> None:
        self.quality_model = quality_model or QualityModel()
        self.on_point_updates = on_point_updates
        self.on_diagnostics = on_diagnostics
        self._configs: Dict[str, EndpointPollConfig] = {}
        self._states: Dict[str, EndpointRuntimeState] = {}
        self._tasks: List[asyncio.Task] = []
        self._stopped = asyncio.Event()

    def add_endpoint(self, config: EndpointPollConfig) -> None:
        """Add an endpoint to poll."""
        self._configs[config.endpoint_id] = config
        self._states[config.endpoint_id] = EndpointRuntimeState()

    def get_state(self, endpoint_id: str) -> EndpointRuntimeState:
        """Get current runtime state for an endpoint."""
        return self._states[endpoint_id]

    async def start(self) -> None:
        """Start polling all configured endpoints."""
        for eid, cfg in self._configs.items():
            task = asyncio.create_task(self._run_endpoint_loop(eid, cfg))
            self._tasks.append(task)

    async def stop(self) -> None:
        """Stop all polling loops."""
        self._stopped.set()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _run_endpoint_loop(
        self, endpoint_id: str, cfg: EndpointPollConfig
    ) -> None:
        """Main polling loop for a single endpoint."""
        while not self._stopped.is_set():
            start = now_utc()
            state = self._states[endpoint_id]
            state.last_poll_started = start

            try:
                await self._poll_once(endpoint_id, cfg, state)
            except Exception as exc:
                state.consecutive_failures += 1
                state.last_fault = repr(exc)
            finally:
                # Emit diagnostics update
                await self._emit_diagnostics(endpoint_id)

            # Sleep for remaining interval time
            elapsed = (now_utc() - start).total_seconds()
            sleep_for = max(0.0, cfg.poll_interval_sec - elapsed)
            await asyncio.sleep(sleep_for)

    async def _poll_once(
        self,
        endpoint_id: str,
        cfg: EndpointPollConfig,
        state: EndpointRuntimeState,
    ) -> None:
        """
        Execute a single poll with retries.

        Updates state and invokes callbacks on success/failure.
        """
        points = cfg.points
        point_names = [p.address.point_name for p in points]

        attempt = 0
        exc: Exception | None = None

        # Retry loop
        while attempt < cfg.max_retries:
            attempt += 1
            try:
                values, rtt_ms = await self._do_single_request(
                    endpoint_id, cfg, point_names, points
                )

                # Success - update state
                state.last_success = now_utc()
                state.last_rtt_ms = rtt_ms
                state.consecutive_failures = 0

                # Classify comms state
                comms_state = self.quality_model.classify_comms_state(
                    last_success=state.last_success,
                    now=now_utc(),
                    consecutive_failures=state.consecutive_failures,
                )
                state.health = comms_state

                # Dispatch point updates
                if self.on_point_updates:
                    await self.on_point_updates(values)

                return

            except Exception as e:
                exc = e
                state.consecutive_failures += 1

        # All retries failed - update health state
        comms_state = self.quality_model.classify_comms_state(
            last_success=state.last_success,
            now=now_utc(),
            consecutive_failures=state.consecutive_failures,
        )
        state.health = comms_state
        state.last_fault = repr(exc)

    async def _do_single_request(
        self,
        endpoint_id: str,
        cfg: EndpointPollConfig,
        point_names: List[str],
        point_defs: List[PointDef],
    ) -> tuple[List[PointValue], float]:
        """
        Execute a single poll request and return decoded point values.

        Returns:
            Tuple of (point values, RTT in milliseconds)

        Raises:
            TimeoutError: If request times out
            ConnectionError: If connection fails
            ValueError: If response is invalid
        """
        # Open connection
        reader, writer = await asyncio.open_connection(cfg.host, cfg.port)
        req_id = str(uuid.uuid4())
        payload = encode_poll_request(req_id, point_names)

        t0 = now_utc()
        writer.write(payload)
        await writer.drain()

        try:
            # Wait for response with timeout
            raw = await asyncio.wait_for(reader.readline(), timeout=cfg.timeout_sec)
            if not raw:
                raise TimeoutError("No response bytes")
        finally:
            writer.close()
            await writer.wait_closed()

        t1 = now_utc()
        rtt_ms = (t1 - t0).total_seconds() * 1000.0

        # Decode response
        resp = decode_poll_response(raw)
        now = now_utc()

        # Map raw samples to PointValue objects with quality
        def_by_name = {p.address.point_name: p for p in point_defs}

        values: List[PointValue] = []
        for sample in resp.points:
            pd = def_by_name.get(sample.name)
            if pd is None:
                continue

            # Classify quality based on comms state and sample age
            comms_state = self.quality_model.classify_comms_state(
                last_success=t1,
                now=now,
                consecutive_failures=0,
            )

            q = self.quality_model.classify_point_quality(
                comms_state=comms_state,
                sample_ts=resp.device_ts,
                now=now,
            )

            # Optional: check for clock drift and adjust quality
            drift_sec = abs((now - resp.device_ts).total_seconds())
            if drift_sec > 5.0:  # More than 5 seconds drift
                # Could downgrade quality here if desired
                pass

            values.append(
                PointValue(
                    definition=pd,
                    value=sample.value,
                    quality=q,
                    server_ts=now,
                    device_ts=resp.device_ts,
                    source="POLL",
                    sequence_num=resp.sequence,
                )
            )

        return values, rtt_ms

    async def _emit_diagnostics(self, endpoint_id: str) -> None:
        """Emit diagnostics update for an endpoint."""
        if not self.on_diagnostics:
            return
        state = self._states[endpoint_id]
        await self.on_diagnostics(endpoint_id, state)
