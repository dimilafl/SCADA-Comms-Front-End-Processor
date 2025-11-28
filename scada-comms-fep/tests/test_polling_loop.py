"""Tests for polling engine integration."""

import asyncio
import pytest

import sys
sys.path.insert(0, '/home/user/SCADA-Comms-Front-End-Processor/scada-comms-fep')

from fep.models import PointAddress, PointDef, QualityFlag
from fep.endpoint_sim import EndpointSimulator, EndpointConfig, SimPoint
from fep.poller import PollingEngine, EndpointPollConfig
from fep.quality import CommsState


@pytest.mark.asyncio
async def test_successful_poll():
    """Test that polling engine successfully polls an endpoint."""
    # Setup endpoint simulator
    endpoint_config = EndpointConfig(
        endpoint_id="TEST_RTU",
        host="127.0.0.1",
        port=9999,
        base_latency_ms=10,
        jitter_ms=5,
        drop_probability=0.0,  # No drops for this test
        points=[
            SimPoint(name="TEST_PT", type="analog", value=100.0),
        ],
    )

    endpoint = EndpointSimulator(endpoint_config)
    await endpoint.start()

    try:
        # Setup polling engine
        received_updates = []

        async def capture_updates(updates):
            received_updates.extend(updates)

        engine = PollingEngine(on_point_updates=capture_updates)

        poll_config = EndpointPollConfig(
            endpoint_id="TEST_RTU",
            host="127.0.0.1",
            port=9999,
            poll_interval_sec=0.5,
            timeout_sec=1.0,
            max_retries=2,
            points=[
                PointDef(
                    address=PointAddress(
                        endpoint_id="TEST_RTU", point_name="TEST_PT"
                    ),
                    point_type="analog",
                    eng_units="units",
                ),
            ],
        )

        engine.add_endpoint(poll_config)
        await engine.start()

        # Wait for at least one poll
        await asyncio.sleep(1.0)

        await engine.stop()

        # Verify we received updates
        assert len(received_updates) > 0

        # Check first update
        update = received_updates[0]
        assert update.definition.address.point_name == "TEST_PT"
        assert isinstance(update.value, float)
        assert update.quality == QualityFlag.GOOD
        assert update.source == "POLL"

        # Check runtime state
        state = engine.get_state("TEST_RTU")
        assert state.last_success is not None
        assert state.consecutive_failures == 0
        assert state.health == CommsState.HEALTHY
        assert state.last_rtt_ms is not None
        assert state.last_rtt_ms > 0

    finally:
        await endpoint.stop()


@pytest.mark.asyncio
async def test_failed_poll_timeout():
    """Test polling behavior when endpoint times out."""
    # Don't start an endpoint - connection will fail

    received_updates = []

    async def capture_updates(updates):
        received_updates.extend(updates)

    engine = PollingEngine(on_point_updates=capture_updates)

    poll_config = EndpointPollConfig(
        endpoint_id="MISSING_RTU",
        host="127.0.0.1",
        port=9998,  # No server on this port
        poll_interval_sec=0.5,
        timeout_sec=0.2,
        max_retries=2,
        points=[
            PointDef(
                address=PointAddress(
                    endpoint_id="MISSING_RTU", point_name="TEST_PT"
                ),
                point_type="analog",
            ),
        ],
    )

    engine.add_endpoint(poll_config)
    await engine.start()

    # Wait for retries to complete
    await asyncio.sleep(1.5)

    await engine.stop()

    # Should have no successful updates
    assert len(received_updates) == 0

    # Check runtime state shows failures
    state = engine.get_state("MISSING_RTU")
    assert state.consecutive_failures > 0
    assert state.health == CommsState.COMM_LOSS
    assert state.last_fault is not None


@pytest.mark.asyncio
async def test_multiple_endpoints():
    """Test polling multiple endpoints concurrently."""
    # Setup two endpoints
    endpoint1_config = EndpointConfig(
        endpoint_id="RTU_A",
        host="127.0.0.1",
        port=9991,
        base_latency_ms=10,
        jitter_ms=5,
        drop_probability=0.0,
        points=[SimPoint(name="PT_A", type="analog", value=50.0)],
    )

    endpoint2_config = EndpointConfig(
        endpoint_id="RTU_B",
        host="127.0.0.1",
        port=9992,
        base_latency_ms=10,
        jitter_ms=5,
        drop_probability=0.0,
        points=[SimPoint(name="PT_B", type="analog", value=75.0)],
    )

    endpoint1 = EndpointSimulator(endpoint1_config)
    endpoint2 = EndpointSimulator(endpoint2_config)

    await endpoint1.start()
    await endpoint2.start()

    try:
        received_updates = []

        async def capture_updates(updates):
            received_updates.extend(updates)

        engine = PollingEngine(on_point_updates=capture_updates)

        # Add both endpoints
        for eid, port, pt_name in [
            ("RTU_A", 9991, "PT_A"),
            ("RTU_B", 9992, "PT_B"),
        ]:
            poll_config = EndpointPollConfig(
                endpoint_id=eid,
                host="127.0.0.1",
                port=port,
                poll_interval_sec=0.5,
                timeout_sec=1.0,
                points=[
                    PointDef(
                        address=PointAddress(endpoint_id=eid, point_name=pt_name),
                        point_type="analog",
                    ),
                ],
            )
            engine.add_endpoint(poll_config)

        await engine.start()

        # Wait for polls
        await asyncio.sleep(1.0)

        await engine.stop()

        # Should have updates from both endpoints
        point_names = {u.definition.address.point_name for u in received_updates}
        assert "PT_A" in point_names
        assert "PT_B" in point_names

        # Both should be healthy
        assert engine.get_state("RTU_A").health == CommsState.HEALTHY
        assert engine.get_state("RTU_B").health == CommsState.HEALTHY

    finally:
        await endpoint1.stop()
        await endpoint2.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
