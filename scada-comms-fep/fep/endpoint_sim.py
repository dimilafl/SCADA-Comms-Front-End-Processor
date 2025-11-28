"""
Virtual endpoint simulator (RTU/PLC).

Simulates field devices with configurable:
- Latency and jitter
- Packet drops
- Device clock drift
- Point value variations
"""

import asyncio
import random
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List

from .protocol import ISO_FMT
from .timebase import now_utc


@dataclass
class SimPoint:
    """Simulated point with value."""
    name: str
    type: str  # "analog" or "digital"
    value: float | bool


@dataclass
class EndpointConfig:
    """Configuration for a virtual endpoint."""
    endpoint_id: str
    host: str = "127.0.0.1"
    port: int = 9001
    base_latency_ms: int = 50
    jitter_ms: int = 20
    drop_probability: float = 0.05
    device_time_drift_ms: int = 0

    points: List[SimPoint] = field(default_factory=list)


class EndpointSimulator:
    """
    Virtual RTU/PLC that responds to poll requests over TCP.

    Simulates realistic field device behavior including network delays,
    packet drops, and device clock drift.
    """

    def __init__(self, config: EndpointConfig) -> None:
        self.config = config
        self.sequence = 0
        self._server: asyncio.base_events.Server | None = None
        self._points: Dict[str, SimPoint] = {p.name: p for p in config.points}

    async def start(self) -> None:
        """Start the TCP server for this endpoint."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.config.host,
            self.config.port,
        )
        print(
            f"[{self.config.endpoint_id}] Started on "
            f"{self.config.host}:{self.config.port}"
        )

    async def stop(self) -> None:
        """Stop the TCP server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle incoming client connections."""
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break

                # Simulate latency, jitter, and packet drops
                await self._maybe_sleep_and_respond(raw, writer)
        finally:
            writer.close()
            await writer.wait_closed()

    async def _maybe_sleep_and_respond(
        self, raw: bytes, writer: asyncio.StreamWriter
    ) -> None:
        """
        Process request with simulated network conditions.

        May drop the request silently to simulate timeout conditions.
        """
        # Simulate packet drop
        if random.random() < self.config.drop_probability:
            # Silent drop to simulate timeout
            return

        # Simulate latency + jitter
        base = self.config.base_latency_ms
        jitter = random.randint(-self.config.jitter_ms, self.config.jitter_ms)
        await asyncio.sleep(max(0, (base + jitter) / 1000.0))

        # Decode request for point list
        req = json.loads(raw.decode("utf-8"))
        points_req = req.get("points", [])

        # Apply device clock drift
        now = now_utc() + timedelta(
            milliseconds=self.config.device_time_drift_ms
        )
        self.sequence += 1

        # Build response with current point values
        points_out = []
        for name in points_req:
            p = self._points.get(name)
            if p is None:
                continue

            # Mutate analog values slightly to simulate real sensors
            if p.type == "analog":
                p.value = float(p.value) + random.uniform(-0.5, 0.5)
            elif p.type == "digital":
                # Occasionally toggle digital values
                if random.random() < 0.01:
                    p.value = not bool(p.value)

            points_out.append({"name": p.name, "type": p.type, "value": p.value})

        # Build and send response
        payload = {
            "type": "poll_response",
            "request_id": req["request_id"],
            "endpoint_id": self.config.endpoint_id,
            "device_ts": now.strftime(ISO_FMT),
            "seq": self.sequence,
            "points": points_out,
        }

        writer.write((json.dumps(payload) + "\n").encode("utf-8"))
        await writer.drain()
