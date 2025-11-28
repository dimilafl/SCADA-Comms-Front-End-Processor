"""Quality model and communications state classification for SCADA systems."""

from enum import Enum
from datetime import datetime, timedelta
from .models import QualityFlag


class CommsState(Enum):
    """Communications health state for an endpoint."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    COMM_LOSS = "COMM_LOSS"


class QualityModel:
    """
    SCADA-style quality classification logic.

    Maps communication failures and sample age to quality flags,
    independent of transport protocol.
    """

    def __init__(
        self,
        stale_threshold: timedelta = timedelta(seconds=10),
        comm_loss_threshold: timedelta = timedelta(seconds=30),
        degraded_retry_threshold: int = 2,
    ) -> None:
        self.stale_threshold = stale_threshold
        self.comm_loss_threshold = comm_loss_threshold
        self.degraded_retry_threshold = degraded_retry_threshold

    def classify_comms_state(
        self,
        last_success: datetime | None,
        now: datetime,
        consecutive_failures: int,
    ) -> CommsState:
        """
        Classify endpoint communications health.

        Args:
            last_success: Timestamp of last successful poll, or None if never succeeded
            now: Current timestamp
            consecutive_failures: Number of consecutive failed poll attempts

        Returns:
            CommsState indicating endpoint health
        """
        if last_success is None:
            return CommsState.COMM_LOSS

        delta = now - last_success
        if delta >= self.comm_loss_threshold:
            return CommsState.COMM_LOSS

        if consecutive_failures >= self.degraded_retry_threshold:
            return CommsState.DEGRADED

        return CommsState.HEALTHY

    def classify_point_quality(
        self,
        comms_state: CommsState,
        sample_ts: datetime,
        now: datetime,
        forced: bool = False,
    ) -> QualityFlag:
        """
        Classify point data quality based on comms state and sample age.

        Args:
            comms_state: Current endpoint communications state
            sample_ts: Timestamp when the sample was acquired
            now: Current timestamp
            forced: Whether the value has been manually forced

        Returns:
            QualityFlag for the point value
        """
        if forced:
            return QualityFlag.FORCED

        if comms_state == CommsState.COMM_LOSS:
            return QualityFlag.COMM_LOSS

        age = now - sample_ts
        if age >= self.stale_threshold:
            return QualityFlag.STALE

        if comms_state == CommsState.DEGRADED:
            return QualityFlag.UNCERTAIN

        return QualityFlag.GOOD
