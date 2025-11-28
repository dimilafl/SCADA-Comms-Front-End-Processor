"""Core data models for SCADA FEP point updates."""

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional
from datetime import datetime


PointType = Literal["analog", "digital"]


@dataclass(frozen=True)
class PointAddress:
    """Unique identifier for a point in the SCADA system."""
    endpoint_id: str
    point_name: str  # "PT_101", "RUN_FB", etc.


@dataclass
class PointDef:
    """Point definition with metadata."""
    address: PointAddress
    point_type: PointType
    eng_units: Optional[str] = None
    description: Optional[str] = None


class QualityFlag(Enum):
    """SCADA-style quality flags for point values."""
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    COMM_LOSS = "COMM_LOSS"
    STALE = "STALE"
    FORCED = "FORCED"


@dataclass
class PointValue:
    """Complete point update package with value, quality, and timestamps."""
    definition: PointDef
    value: float | bool
    quality: QualityFlag
    server_ts: datetime
    device_ts: Optional[datetime] = None
    source: str = "POLL"  # or "MANUAL", "SIM"
    sequence_num: Optional[int] = None
