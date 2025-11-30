#!/usr/bin/env python3
"""
SCADA FEP Web Demo Application.

Demonstrates the complete system with web UI:
- Multiple virtual endpoints with different network characteristics
- Concurrent polling with quality classification
- Real-time web dashboard with WebSocket updates
- REST API for diagnostics and point history
"""

import asyncio
import sys

sys.path.insert(0, '/home/user/SCADA-Comms-Front-End-Processor/scada-comms-fep')

import uvicorn

from fep.endpoint_sim import EndpointSimulator, EndpointConfig, SimPoint
from fep.poller import PollingEngine, EndpointPollConfig
from fep.dispatcher import Dispatcher
from fep.models import PointAddress, PointDef
from web.server import app, diagnostics_callback, point_updates_callback


async def start_endpoints():
    """Start virtual RTU/PLC endpoints."""
    print("\n=== Starting Virtual Endpoints ===")

    # RTU_1: Healthy endpoint with low latency
    rtu1 = EndpointSimulator(
        EndpointConfig(
            endpoint_id="RTU_1",
            host="127.0.0.1",
            port=9001,
            base_latency_ms=80,
            jitter_ms=40,
            drop_probability=0.10,  # 10% packet loss
            device_time_drift_ms=0,
            points=[
                SimPoint(name="PT_101", type="analog", value=700.0),
                SimPoint(name="TEMP_01", type="analog", value=185.5),
                SimPoint(name="RUN_FB", type="digital", value=False),
            ],
        )
    )
    await rtu1.start()

    # RTU_2: Endpoint with moderate characteristics
    rtu2 = EndpointSimulator(
        EndpointConfig(
            endpoint_id="RTU_2",
            host="127.0.0.1",
            port=9002,
            base_latency_ms=30,
            jitter_ms=10,
            drop_probability=0.02,  # 2% packet loss
            device_time_drift_ms=200,  # 200ms clock drift
            points=[
                SimPoint(name="PT_201", type="analog", value=500.0),
                SimPoint(name="FLOW_01", type="analog", value=234.8),
                SimPoint(name="VALVE_OPEN", type="digital", value=True),
            ],
        )
    )
    await rtu2.start()

    # RTU_3: Unreliable endpoint (will show DEGRADED/COMM_LOSS)
    rtu3 = EndpointSimulator(
        EndpointConfig(
            endpoint_id="RTU_3",
            host="127.0.0.1",
            port=9003,
            base_latency_ms=200,
            jitter_ms=100,
            drop_probability=0.35,  # 35% packet loss
            device_time_drift_ms=-500,  # -500ms drift
            points=[
                SimPoint(name="PRESSURE", type="analog", value=14.7),
                SimPoint(name="PUMP_RUN", type="digital", value=True),
            ],
        )
    )
    await rtu3.start()

    return [rtu1, rtu2, rtu3]


async def main():
    """Main application entry point."""
    print("=" * 70)
    print("SCADA Front-End Processor - Web Demo")
    print("=" * 70)

    # Start dispatcher
    dispatcher = Dispatcher(max_queue=1000)
    await dispatcher.start()
    print("✓ Dispatcher started")

    # Create polling engine with web callbacks
    async def on_point_updates(updates):
        """Handle point updates from poller."""
        # Send to web UI
        await point_updates_callback(updates)
        # Could also send to dispatcher for other subscribers
        # await dispatcher.publish(updates)

    async def on_diagnostics(endpoint_id, state):
        """Handle diagnostics updates from poller."""
        await diagnostics_callback(endpoint_id, state, dispatcher)

    engine = PollingEngine(
        on_point_updates=on_point_updates,
        on_diagnostics=on_diagnostics,
    )

    # Configure polling for RTU_1
    engine.add_endpoint(
        EndpointPollConfig(
            endpoint_id="RTU_1",
            host="127.0.0.1",
            port=9001,
            poll_interval_sec=1.0,
            timeout_sec=0.5,
            max_retries=3,
            points=[
                PointDef(
                    PointAddress("RTU_1", "PT_101"),
                    point_type="analog",
                    eng_units="psi",
                    description="Pressure Transmitter 101",
                ),
                PointDef(
                    PointAddress("RTU_1", "TEMP_01"),
                    point_type="analog",
                    eng_units="°F",
                    description="Temperature 01",
                ),
                PointDef(
                    PointAddress("RTU_1", "RUN_FB"),
                    point_type="digital",
                    description="Run Feedback",
                ),
            ],
        )
    )

    # Configure polling for RTU_2
    engine.add_endpoint(
        EndpointPollConfig(
            endpoint_id="RTU_2",
            host="127.0.0.1",
            port=9002,
            poll_interval_sec=1.5,
            timeout_sec=1.0,
            max_retries=3,
            points=[
                PointDef(
                    PointAddress("RTU_2", "PT_201"),
                    point_type="analog",
                    eng_units="psi",
                    description="Pressure Transmitter 201",
                ),
                PointDef(
                    PointAddress("RTU_2", "FLOW_01"),
                    point_type="analog",
                    eng_units="GPM",
                    description="Flow Meter 01",
                ),
                PointDef(
                    PointAddress("RTU_2", "VALVE_OPEN"),
                    point_type="digital",
                    description="Valve Open Status",
                ),
            ],
        )
    )

    # Configure polling for RTU_3 (unreliable)
    engine.add_endpoint(
        EndpointPollConfig(
            endpoint_id="RTU_3",
            host="127.0.0.1",
            port=9003,
            poll_interval_sec=2.0,
            timeout_sec=1.5,
            max_retries=2,
            points=[
                PointDef(
                    PointAddress("RTU_3", "PRESSURE"),
                    point_type="analog",
                    eng_units="psi",
                    description="Pressure Gauge",
                ),
                PointDef(
                    PointAddress("RTU_3", "PUMP_RUN"),
                    point_type="digital",
                    description="Pump Running",
                ),
            ],
        )
    )

    print("✓ Polling engine configured")

    # Start endpoints
    endpoints = await start_endpoints()

    # Start polling engine
    await engine.start()
    print("✓ Polling engine started")

    print("\n" + "=" * 70)
    print("Web UI: http://localhost:8000")
    print("=" * 70)
    print("\nExpected behavior:")
    print("  RTU_1: Mostly HEALTHY (green) with occasional DEGRADED")
    print("  RTU_2: HEALTHY (green) most of the time")
    print("  RTU_3: Frequently DEGRADED (yellow) or COMM_LOSS (red)")
    print("\nPress Ctrl+C to stop\n")

    # Run uvicorn server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False,  # Reduce noise
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except KeyboardInterrupt:
        print("\n\nShutting down...")

    # Cleanup
    await engine.stop()
    await dispatcher.stop()
    for ep in endpoints:
        await ep.stop()

    print("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
