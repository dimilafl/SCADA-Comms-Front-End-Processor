"""Tests for SCADA protocol encoding and decoding."""

import json
import pytest
from datetime import datetime, timezone

import sys
sys.path.insert(0, '/home/user/SCADA-Comms-Front-End-Processor/scada-comms-fep')

from fep.protocol import (
    encode_poll_request,
    decode_poll_response,
    PollResponse,
    RawPointSample,
    ISO_FMT,
)


def test_encode_poll_request():
    """Test encoding of poll request to JSON bytes."""
    request_id = "test-123"
    points = ["PT_101", "RUN_FB"]

    encoded = encode_poll_request(request_id, points)

    # Should be valid JSON with newline
    assert encoded.endswith(b"\n")
    decoded = json.loads(encoded.decode("utf-8"))

    assert decoded["type"] == "poll"
    assert decoded["request_id"] == request_id
    assert decoded["points"] == points


def test_decode_poll_response():
    """Test decoding of poll response from JSON bytes."""
    device_ts = datetime(2025, 11, 28, 10, 12, 0, 123456, tzinfo=timezone.utc)
    response_json = {
        "type": "poll_response",
        "request_id": "test-456",
        "endpoint_id": "RTU_1",
        "device_ts": device_ts.strftime(ISO_FMT),
        "seq": 42,
        "points": [
            {"name": "PT_101", "type": "analog", "value": 723.4},
            {"name": "RUN_FB", "type": "digital", "value": True},
        ],
    }

    encoded = (json.dumps(response_json) + "\n").encode("utf-8")
    response = decode_poll_response(encoded)

    assert response.request_id == "test-456"
    assert response.endpoint_id == "RTU_1"
    assert response.device_ts == device_ts
    assert response.sequence == 42
    assert len(response.points) == 2

    assert response.points[0].name == "PT_101"
    assert response.points[0].type == "analog"
    assert response.points[0].value == 723.4

    assert response.points[1].name == "RUN_FB"
    assert response.points[1].type == "digital"
    assert response.points[1].value is True


def test_decode_invalid_type():
    """Test that decoding raises ValueError for wrong message type."""
    invalid_json = {
        "type": "invalid",
        "request_id": "test-789",
    }

    encoded = (json.dumps(invalid_json) + "\n").encode("utf-8")

    with pytest.raises(ValueError, match="Not a poll_response frame"):
        decode_poll_response(encoded)


def test_decode_missing_fields():
    """Test that decoding raises KeyError for missing required fields."""
    incomplete_json = {
        "type": "poll_response",
        "request_id": "test-999",
        # Missing endpoint_id, device_ts, seq, points
    }

    encoded = (json.dumps(incomplete_json) + "\n").encode("utf-8")

    with pytest.raises(KeyError):
        decode_poll_response(encoded)


def test_round_trip():
    """Test that request encoding and response decoding work together."""
    # Encode request
    request_id = "round-trip-1"
    points = ["TEMP_01", "PRESSURE_02"]
    request = encode_poll_request(request_id, points)

    # Verify request is valid
    req_obj = json.loads(request.decode("utf-8"))
    assert req_obj["request_id"] == request_id
    assert req_obj["points"] == points

    # Decode response
    device_ts = datetime(2025, 11, 28, 15, 30, 45, 678901, tzinfo=timezone.utc)
    response_json = {
        "type": "poll_response",
        "request_id": request_id,
        "endpoint_id": "RTU_2",
        "device_ts": device_ts.strftime(ISO_FMT),
        "seq": 100,
        "points": [
            {"name": "TEMP_01", "type": "analog", "value": 98.6},
            {"name": "PRESSURE_02", "type": "analog", "value": 14.7},
        ],
    }

    response_bytes = (json.dumps(response_json) + "\n").encode("utf-8")
    response = decode_poll_response(response_bytes)

    assert response.request_id == request_id
    assert len(response.points) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
