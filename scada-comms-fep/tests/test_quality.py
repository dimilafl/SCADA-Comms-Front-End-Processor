"""Tests for quality classification logic."""

import pytest
from datetime import datetime, timedelta, timezone

import sys
sys.path.insert(0, '/home/user/SCADA-Comms-Front-End-Processor/scada-comms-fep')

from fep.quality import QualityModel, CommsState
from fep.models import QualityFlag


def test_comms_state_healthy():
    """Test classification of healthy communications."""
    model = QualityModel(
        stale_threshold=timedelta(seconds=10),
        comm_loss_threshold=timedelta(seconds=30),
        degraded_retry_threshold=2,
    )

    now = datetime.now(timezone.utc)
    last_success = now - timedelta(seconds=5)

    state = model.classify_comms_state(
        last_success=last_success,
        now=now,
        consecutive_failures=0,
    )

    assert state == CommsState.HEALTHY


def test_comms_state_degraded():
    """Test classification of degraded communications (retries happening)."""
    model = QualityModel(degraded_retry_threshold=2)

    now = datetime.now(timezone.utc)
    last_success = now - timedelta(seconds=5)

    state = model.classify_comms_state(
        last_success=last_success,
        now=now,
        consecutive_failures=2,
    )

    assert state == CommsState.DEGRADED


def test_comms_state_comm_loss_timeout():
    """Test comm loss due to timeout exceeding threshold."""
    model = QualityModel(comm_loss_threshold=timedelta(seconds=30))

    now = datetime.now(timezone.utc)
    last_success = now - timedelta(seconds=40)  # 40 seconds ago

    state = model.classify_comms_state(
        last_success=last_success,
        now=now,
        consecutive_failures=5,
    )

    assert state == CommsState.COMM_LOSS


def test_comms_state_comm_loss_never_succeeded():
    """Test comm loss when endpoint has never successfully polled."""
    model = QualityModel()

    now = datetime.now(timezone.utc)

    state = model.classify_comms_state(
        last_success=None,
        now=now,
        consecutive_failures=10,
    )

    assert state == CommsState.COMM_LOSS


def test_point_quality_good():
    """Test GOOD quality flag for healthy comms and fresh data."""
    model = QualityModel(stale_threshold=timedelta(seconds=10))

    now = datetime.now(timezone.utc)
    sample_ts = now - timedelta(seconds=2)  # 2 seconds old

    quality = model.classify_point_quality(
        comms_state=CommsState.HEALTHY,
        sample_ts=sample_ts,
        now=now,
        forced=False,
    )

    assert quality == QualityFlag.GOOD


def test_point_quality_uncertain():
    """Test UNCERTAIN quality for degraded comms."""
    model = QualityModel()

    now = datetime.now(timezone.utc)
    sample_ts = now - timedelta(seconds=2)

    quality = model.classify_point_quality(
        comms_state=CommsState.DEGRADED,
        sample_ts=sample_ts,
        now=now,
        forced=False,
    )

    assert quality == QualityFlag.UNCERTAIN


def test_point_quality_stale():
    """Test STALE quality for old data."""
    model = QualityModel(stale_threshold=timedelta(seconds=10))

    now = datetime.now(timezone.utc)
    sample_ts = now - timedelta(seconds=15)  # 15 seconds old

    quality = model.classify_point_quality(
        comms_state=CommsState.HEALTHY,
        sample_ts=sample_ts,
        now=now,
        forced=False,
    )

    assert quality == QualityFlag.STALE


def test_point_quality_comm_loss():
    """Test COMM_LOSS quality flag."""
    model = QualityModel()

    now = datetime.now(timezone.utc)
    sample_ts = now - timedelta(seconds=2)

    quality = model.classify_point_quality(
        comms_state=CommsState.COMM_LOSS,
        sample_ts=sample_ts,
        now=now,
        forced=False,
    )

    assert quality == QualityFlag.COMM_LOSS


def test_point_quality_forced():
    """Test FORCED quality flag takes precedence."""
    model = QualityModel()

    now = datetime.now(timezone.utc)
    sample_ts = now - timedelta(seconds=100)  # Very old

    quality = model.classify_point_quality(
        comms_state=CommsState.COMM_LOSS,  # Even with comm loss
        sample_ts=sample_ts,
        now=now,
        forced=True,  # FORCED should take precedence
    )

    assert quality == QualityFlag.FORCED


def test_quality_thresholds_customization():
    """Test that custom thresholds work correctly."""
    model = QualityModel(
        stale_threshold=timedelta(seconds=5),
        comm_loss_threshold=timedelta(seconds=15),
        degraded_retry_threshold=1,
    )

    now = datetime.now(timezone.utc)

    # Should be degraded with just 1 failure
    state = model.classify_comms_state(
        last_success=now - timedelta(seconds=3),
        now=now,
        consecutive_failures=1,
    )
    assert state == CommsState.DEGRADED

    # Should be comm loss after 15 seconds
    state = model.classify_comms_state(
        last_success=now - timedelta(seconds=20),
        now=now,
        consecutive_failures=0,
    )
    assert state == CommsState.COMM_LOSS

    # Should be stale after 5 seconds
    sample_ts = now - timedelta(seconds=6)
    quality = model.classify_point_quality(
        comms_state=CommsState.HEALTHY,
        sample_ts=sample_ts,
        now=now,
    )
    assert quality == QualityFlag.STALE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
