#!/usr/bin/env python3
"""
SCADA FEP Demo Application.

Demonstrates:
- Multiple virtual endpoints with different network characteristics
- Concurrent polling with quality classification
- Real-time diagnostics console
- Dispatcher queue and subscriber pattern
"""

import asyncio
import sys

sys.path.insert(0, '/home/user/SCADA-Comms-Front-End-Processor/scada-comms-fep')

from fep.models import PointAddress, PointDef
from fep.endpoint_sim import EndpointSimulator, EndpointConfig, SimPoint
from fep.poller import PollingEngine, EndpointPollConfig
from fep.dispatcher import Dispatcher
from ui.console import DiagnosticsConsole


async def point_update_subscriber(updates):
    """Example subscriber that logs point updates."""
    # In a real system, this would be a historian, lifecycle sim, or alarm engine
    pass


async def main():
    """Main demo application."""
    print("Starting SCADA Front-End Processor Demo...")
    print("=" * 60)

    # --- Setup Dispatcher ---
    dispatcher = Dispatcher(max_queue=1000)
    await dispatcher.start()

    # Subscribe a simple handler
    dispatcher.subscribe(point_update_subscriber)

    # --- Setup Diagnostics Console ---
    console = DiagnosticsConsole(dispatcher)

    async def diagnostics_callback(endpoint_id: str, state):
        """Callback to update console state."""
        console.update_state(endpoint_id, state)

    # --- Setup Polling Engine ---
    engine = PollingEngine(
        on_point_updates=dispatcher.publish,
        on_diagnostics=diagnostics_callback,
    )

    # --- Create Virtual Endpoints ---
    endpoints = []

    # RTU_1: Healthy endpoint with low latency
    rtu1_config = EndpointConfig(
        endpoint_id="RTU_1",
        host="127.0.0.1",
        port=9001,
        base_latency_ms=30,
        jitter_ms=10,
        drop_probability=0.02,  # 2% packet loss
        device_time_drift_ms=0,
        points=[
            SimPoint(name="PT_101", type="analog", value=723.4),
            SimPoint(name="TEMP_01", type="analog", value=98.6),
            SimPoint(name="RUN_FB", type="digital", value=True),
        ],
    )
    rtu1 = EndpointSimulator(rtu1_config)
    endpoints.append(rtu1)

    # RTU_2: Endpoint with higher latency and jitter
    rtu2_config = EndpointConfig(
        endpoint_id="RTU_2",
        host="127.0.0.1",
        port=9002,
        base_latency_ms=100,
        jitter_ms=50,
        drop_probability=0.05,  # 5% packet loss
        device_time_drift_ms=500,  # 500ms clock drift
        points=[
            SimPoint(name="FLOW_01", type="analog", value=456.7),
            SimPoint(name="VALVE_POS", type="analog", value=75.0),
            SimPoint(name="ALARM", type="digital", value=False),
        ],
    )
    rtu2 = EndpointSimulator(rtu2_config)
    endpoints.append(rtu2)

    # RTU_3: Unreliable endpoint with high packet loss
    rtu3_config = EndpointConfig(
        endpoint_id="RTU_3",
        host="127.0.0.1",
        port=9003,
        base_latency_ms=200,
        jitter_ms=100,
        drop_probability=0.30,  # 30% packet loss - will show DEGRADED/COMM_LOSS
        device_time_drift_ms=-1000,  # -1 second drift
        points=[
            SimPoint(name="PRESSURE", type="analog", value=14.7),
            SimPoint(name="PUMP_RUN", type="digital", value=True),
        ],
    )
    rtu3 = EndpointSimulator(rtu3_config)
    endpoints.append(rtu3)

    # Start all endpoint simulators
    for ep in endpoints:
        await ep.start()

    # --- Configure Polling ---
    # RTU_1: Fast polling (1 second)
    poll_cfg_1 = EndpointPollConfig(
        endpoint_id="RTU_1",
        host="127.0.0.1",
        port=9001,
        poll_interval_sec=1.0,
        timeout_sec=0.5,
        max_retries=3,
        points=[
            PointDef(
                address=PointAddress(endpoint_id="RTU_1", point_name="PT_101"),
                point_type="analog",
                eng_units="psi",
                description="Pressure Transmitter 101",
            ),
            PointDef(
                address=PointAddress(endpoint_id="RTU_1", point_name="TEMP_01"),
                point_type="analog",
                eng_units="°F",
                description="Temperature 01",
            ),
            PointDef(
                address=PointAddress(endpoint_id="RTU_1", point_name="RUN_FB"),
                point_type="digital",
                description="Run Feedback",
            ),
        ],
    )
    engine.add_endpoint(poll_cfg_1)

    # RTU_2: Medium polling (2 seconds)
    poll_cfg_2 = EndpointPollConfig(
        endpoint_id="RTU_2",
        host="127.0.0.1",
        port=9002,
        poll_interval_sec=2.0,
        timeout_sec=1.0,
        max_retries=3,
        points=[
            PointDef(
                address=PointAddress(endpoint_id="RTU_2", point_name="FLOW_01"),
                point_type="analog",
                eng_units="GPM",
                description="Flow Meter 01",
            ),
            PointDef(
                address=PointAddress(endpoint_id="RTU_2", point_name="VALVE_POS"),
                point_type="analog",
                eng_units="%",
                description="Valve Position",
            ),
            PointDef(
                address=PointAddress(endpoint_id="RTU_2", point_name="ALARM"),
                point_type="digital",
                description="Alarm Status",
            ),
        ],
    )
    engine.add_endpoint(poll_cfg_2)

    # RTU_3: Slow polling (3 seconds) - will show health issues
    poll_cfg_3 = EndpointPollConfig(
        endpoint_id="RTU_3",
        host="127.0.0.1",
        port=9003,
        poll_interval_sec=3.0,
        timeout_sec=1.5,
        max_retries=2,
        points=[
            PointDef(
                address=PointAddress(endpoint_id="RTU_3", point_name="PRESSURE"),
                point_type="analog",
                eng_units="psi",
                description="Pressure Gauge",
            ),
            PointDef(
                address=PointAddress(endpoint_id="RTU_3", point_name="PUMP_RUN"),
                point_type="digital",
                description="Pump Running",
            ),
        ],
    )
    engine.add_endpoint(poll_cfg_3)

    # --- Start Everything ---
    await console.start()
    await engine.start()

    print("FEP is running. Watch the diagnostics console...\n")

    # Run until interrupted
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n\nShutting down...")

    # Cleanup
    await console.stop()
    await engine.stop()
    await dispatcher.stop()

    for ep in endpoints:
        await ep.stop()

    print("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
