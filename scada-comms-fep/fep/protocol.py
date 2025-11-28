"""
SCADA-lite protocol implementation.

Simple text-based protocol using newline-terminated JSON for poll requests/responses.
Transport: TCP with asyncio streams.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List
from datetime import datetime, timezone


ISO_FMT = "%Y-%m-%dT%H:%M:%S.%f"


def encode_poll_request(request_id: str, points: List[str]) -> bytes:
    """
    Encode a poll request for transmission to an endpoint.

    Args:
        request_id: Unique request identifier (typically UUID)
        points: List of point names to poll

    Returns:
        Newline-terminated JSON bytes ready for transmission
    """
    payload = {
        "type": "poll",
        "request_id": request_id,
        "points": points,
    }
    return (json.dumps(payload) + "\n").encode("utf-8")


@dataclass
class RawPointSample:
    """Raw point sample from endpoint before quality processing."""
    name: str
    type: str
    value: Any


@dataclass
class PollResponse:
    """Decoded poll response from an endpoint."""
    request_id: str
    endpoint_id: str
    device_ts: datetime
    sequence: int
    points: List[RawPointSample]


def decode_poll_response(line: bytes) -> PollResponse:
    """
    Decode a poll response from an endpoint.

    Args:
        line: Newline-terminated JSON bytes

    Returns:
        Parsed PollResponse

    Raises:
        ValueError: If the message is not a valid poll_response
        JSONDecodeError: If the JSON is malformed
        KeyError: If required fields are missing
    """
    obj: Dict[str, Any] = json.loads(line.decode("utf-8"))

    if obj.get("type") != "poll_response":
        raise ValueError(f"Not a poll_response frame, got: {obj.get('type')}")

    points = [
        RawPointSample(
            name=p["name"],
            type=p["type"],
            value=p["value"],
        )
        for p in obj["points"]
    ]

    return PollResponse(
        request_id=obj["request_id"],
        endpoint_id=obj["endpoint_id"],
        device_ts=datetime.strptime(obj["device_ts"], ISO_FMT).replace(tzinfo=timezone.utc),
        sequence=int(obj["seq"]),
        points=points,
    )
