"""
Real-time diagnostics console for SCADA FEP.

Displays endpoint health, RTT, failures, and queue depth.
"""

import asyncio
from typing import Dict

import sys
sys.path.insert(0, '/home/user/SCADA-Comms-Front-End-Processor/scada-comms-fep')

from fep.poller import EndpointRuntimeState
from fep.dispatcher import Dispatcher


class DiagnosticsConsole:
    """
    Real-time diagnostics console using ANSI terminal control.

    Updates display every second with current endpoint states and queue depth.
    """

    def __init__(self, dispatcher: Dispatcher) -> None:
        self._states: Dict[str, EndpointRuntimeState] = {}
        self._dispatcher = dispatcher
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    def update_state(self, endpoint_id: str, state: EndpointRuntimeState) -> None:
        """Update state for an endpoint (called from polling engine callback)."""
        self._states[endpoint_id] = state

    async def start(self) -> None:
        """Start the console refresh loop."""
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Stop the console refresh loop."""
        self._stopped.set()
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _loop(self) -> None:
        """Main refresh loop."""
        while not self._stopped.is_set():
            self._render()
            await asyncio.sleep(1.0)

    def _render(self) -> None:
        """Render the console display."""
        # Clear screen and move cursor to home
        print("\033[2J\033[H", end="")

        print("=" * 110)
        print("SCADA Front-End Processor - Real-Time Diagnostics")
        print("=" * 110)
        print()
        print(f"Dispatcher Queue Depth: {self._dispatcher.queue_depth}\n")

        # Table header
        print(
            f"{'Endpoint':<12} {'Health':<12} {'Last Poll':<26} {'RTT(ms)':<10} "
            f"{'Failures':<10} {'Last Fault':<30}"
        )
        print("-" * 110)

        # Sort endpoints by ID for consistent display
        for eid in sorted(self._states.keys()):
            st = self._states[eid]

            # Format fields
            lp = st.last_poll_started.isoformat() if st.last_poll_started else "-"
            rtt = f"{st.last_rtt_ms:.1f}" if st.last_rtt_ms is not None else "-"
            lf = st.consecutive_failures
            fault = (st.last_fault or "")[:28]

            # Color code health status
            health_str = st.health.value
            if st.health.value == "HEALTHY":
                health_str = f"\033[92m{st.health.value}\033[0m"  # Green
            elif st.health.value == "DEGRADED":
                health_str = f"\033[93m{st.health.value}\033[0m"  # Yellow
            elif st.health.value == "COMM_LOSS":
                health_str = f"\033[91m{st.health.value}\033[0m"  # Red

            print(
                f"{eid:<12} {health_str:<20} {lp:<26} {rtt:<10} "
                f"{lf:<10} {fault:<30}"
            )

        print()
        print("Press Ctrl+C to exit")
