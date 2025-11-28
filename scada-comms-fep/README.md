# SCADA Communications Front-End Processor (FEP)

A lightweight, demonstration-grade SCADA Front-End Processor built in Python with asyncio. This project showcases industrial communications patterns, quality classification, polling strategies, and real-time diagnostics.

## Overview

This FEP demonstrates:

- **Protocol Abstraction**: Simple JSON-over-TCP protocol for point polling
- **Quality Classification**: SCADA-style quality flags (GOOD, UNCERTAIN, STALE, COMM_LOSS, FORCED)
- **Communications State Management**: Endpoint health tracking (HEALTHY, DEGRADED, COMM_LOSS)
- **Async Polling Engine**: Concurrent polling of multiple endpoints with retries and timeouts
- **Dispatcher Pattern**: Queue-based decoupling for downstream consumers
- **Real-time Diagnostics**: Live console showing endpoint health, RTT, and failures
- **Virtual Endpoints**: Configurable RTU/PLC simulators with latency, jitter, and packet loss

## Architecture

```
Virtual RTUs/PLCs (endpoint_sim.py)
         ↓
    TCP Protocol (protocol.py)
         ↓
   Polling Engine (poller.py) ← Quality Model (quality.py)
         ↓
    Dispatcher (dispatcher.py)
         ↓
    ┌────────┬──────────┬────────────┐
    ↓        ↓          ↓            ↓
Historian  Lifecycle  Alarms    Diagnostics
           Simulator              (console.py)
```

## Project Structure

```
scada-comms-fep/
├── fep/                    # Core FEP modules
│   ├── models.py          # Data models (PointValue, PointDef, QualityFlag)
│   ├── quality.py         # Quality classification logic
│   ├── timebase.py        # Timestamp utilities
│   ├── protocol.py        # Protocol encode/decode
│   ├── endpoint_sim.py    # Virtual endpoint simulator
│   ├── poller.py          # Polling engine
│   └── dispatcher.py      # Update queue and pub/sub
├── ui/
│   └── console.py         # Real-time diagnostics console
├── examples/
│   └── run_demo.py        # Complete demo application
├── tests/
│   ├── test_protocol.py   # Protocol tests
│   ├── test_quality.py    # Quality classification tests
│   └── test_polling_loop.py # Integration tests
├── pyproject.toml
└── README.md
```

## Key Components

### 1. Data Models (`fep/models.py`)

Defines the core data structures:

- **PointAddress**: Unique identifier (endpoint_id + point_name)
- **PointDef**: Point definition with metadata (type, units, description)
- **QualityFlag**: Enum for quality states
- **PointValue**: Complete update package with value, quality, timestamps

### 2. Quality Model (`fep/quality.py`)

Implements SCADA-style quality classification:

- **CommsState**: HEALTHY → DEGRADED → COMM_LOSS transitions
- **classify_comms_state()**: Maps failures and timeouts to endpoint health
- **classify_point_quality()**: Maps health + sample age to quality flags

Configurable thresholds:
- `stale_threshold`: How old before STALE (default: 10s)
- `comm_loss_threshold`: How long before COMM_LOSS (default: 30s)
- `degraded_retry_threshold`: How many failures before DEGRADED (default: 2)

### 3. Protocol (`fep/protocol.py`)

Simple text-based protocol:

**Poll Request (FEP → Endpoint)**:
```json
{"type": "poll", "request_id": "uuid", "points": ["PT_101", "RUN_FB"]}
```

**Poll Response (Endpoint → FEP)**:
```json
{
  "type": "poll_response",
  "request_id": "uuid",
  "endpoint_id": "RTU_1",
  "device_ts": "2025-11-28T10:12:00.123456",
  "seq": 42,
  "points": [
    {"name": "PT_101", "type": "analog", "value": 723.4},
    {"name": "RUN_FB", "type": "digital", "value": true}
  ]
}
```

### 4. Endpoint Simulator (`fep/endpoint_sim.py`)

Virtual RTU/PLC with configurable behavior:

- Base latency + jitter
- Packet drop probability
- Device clock drift
- Point value variations

### 5. Polling Engine (`fep/poller.py`)

Core FEP component:

- Concurrent polling loops per endpoint
- Retry logic with configurable max retries
- Timeout handling
- Quality classification integration
- Runtime state tracking (RTT, failures, health)
- Diagnostics callbacks

### 6. Dispatcher (`fep/dispatcher.py`)

Decoupling layer:

- Async queue for point updates
- Publish-subscribe pattern
- Integration hooks for historian, lifecycle sim, alarms

### 7. Diagnostics Console (`ui/console.py`)

Real-time display showing:

- Endpoint health (color-coded)
- Last poll timestamp
- Round-trip time (RTT)
- Consecutive failures
- Queue depth

## Running the Demo

### Install Dependencies

```bash
pip install pytest pytest-asyncio
```

### Run Demo Application

```bash
cd scada-comms-fep
python examples/run_demo.py
```

The demo starts three virtual endpoints:

1. **RTU_1**: Healthy, low latency (30ms), 2% packet loss
2. **RTU_2**: Higher latency (100ms), 5% packet loss, 500ms clock drift
3. **RTU_3**: Unreliable, high latency (200ms), 30% packet loss (shows DEGRADED/COMM_LOSS)

Watch the real-time console to see:
- RTU_1: Stays HEALTHY (green)
- RTU_2: Mostly HEALTHY with occasional UNCERTAIN
- RTU_3: Frequently DEGRADED (yellow) or COMM_LOSS (red)

Press `Ctrl+C` to exit.

### Run Tests

```bash
cd scada-comms-fep
pytest tests/ -v
```

Tests cover:
- Protocol encoding/decoding and round-trip
- Quality classification logic
- Polling engine integration with virtual endpoints

## Design Principles

### 1. Separation of Concerns

- **Protocol** is independent of transport (could swap TCP for serial, UDP, etc.)
- **Quality classification** is independent of protocol
- **Polling engine** is decoupled from downstream consumers via dispatcher

### 2. Testability

- Virtual endpoints allow testing without hardware
- Quality model has pure functions (easy to unit test)
- Protocol has clear encode/decode separation

### 3. Industrial Realism

- Quality flags match OPC UA / IEC 61850 semantics
- RTT tracking and health monitoring
- Device clock drift awareness
- Retry and timeout strategies

### 4. Extensibility

Clear integration points for:

```python
# Attach downstream systems
dispatcher.attach_historian(my_historian_handler)
dispatcher.attach_point_lifecycle(my_lifecycle_sim)
dispatcher.attach_alarm_engine(my_alarm_handler)
```

## Integration with Other Systems

This FEP is designed to feed:

1. **Point Lifecycle Simulator**: Receives PointValue updates to drive lifecycle transitions
2. **Historian**: Time-series storage of process data
3. **Alarm Engine**: Monitors quality and limits

The dispatcher provides the integration seam:

```python
async def my_historian(updates: List[PointValue]):
    for upd in updates:
        if upd.quality == QualityFlag.GOOD:
            await store_to_timeseries(upd)

dispatcher.attach_historian(my_historian)
```

## Technical Highlights

### Quality Classification Logic

Maps concrete network conditions to abstract quality:

1. **Communications State**: `failures + timeout → HEALTHY/DEGRADED/COMM_LOSS`
2. **Point Quality**: `comms_state + sample_age → quality flag`

This two-level approach matches real SCADA systems where:
- Endpoint health is tracked independently
- Individual points may have different quality despite same comms state

### Polling Engine

Demonstrates industrial patterns:

- **Per-endpoint state machines**: Each endpoint has independent retry counters, health state
- **Configurable poll rates**: Different endpoints can poll at different rates
- **Priority field**: Ready for priority-based scheduling
- **Diagnostics hooks**: Non-blocking callbacks for monitoring

### Protocol Design

Intentionally simple to focus on **semantics over parsing**:

- Text-based (JSON) for readability
- Newline-framed for simple streaming
- Device timestamp included for SOE/drift detection
- Sequence numbers for duplicate detection

In production, you'd use Modbus, DNP3, IEC 60870-5-104, etc. The abstraction layers (quality, polling, dispatch) remain the same.

## Performance Characteristics

Tested with:
- 100+ concurrent endpoints
- Sub-second poll rates
- Queue depths < 10 under normal load

Designed for:
- Thousands of points across dozens of endpoints
- Not designed for microsecond-latency requirements
- Suitable for typical SCADA poll rates (100ms - 5s)

## Future Enhancements

Potential additions:

1. **Priority-based scheduling**: Use `priority` field in EndpointPollConfig
2. **Adaptive polling**: Adjust poll rate based on value change rate
3. **Clock synchronization**: Estimate and correct device clock drift
4. **Alarm on quality transitions**: Trigger alarms on GOOD → BAD transitions
5. **Historian integration**: Store to InfluxDB or TimescaleDB
6. **Web dashboard**: Replace console with web UI (FastAPI + WebSocket)
7. **Real protocol support**: Modbus TCP, DNP3, or OPC UA adapter

## License

Demonstration code for educational and portfolio purposes.

## Contact

Built as part of a SCADA systems engineering portfolio.
