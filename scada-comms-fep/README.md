# SCADA Comms Front-End Simulator

A virtual SCADA front-end processor (FEP) built in Python with asyncio that demonstrates industrial communications patterns **without real hardware or industrial protocols**. This is a teaching and portfolio project that simulates the behavior of real FEPs (OASyS gateways, Ignition drivers, SEL RTAC poll loops) using simple TCP servers and a JSON line protocol. It showcases the complete data flow: **ingest → validate → normalize → dispatch**.

## Why this exists

This project fills the gap between:
- **PLC logic emulators** (ladder logic simulators, IEC 61131 execution)
- **Point lifecycle / historian / alarm simulators** (process data consumers)

It mirrors real-world SCADA FEP systems:
- **OASyS / Ignition gateways** polling field RTUs
- **AVEVA / Wonderware drivers** managing protocol stacks
- **SEL RTAC poll loops** aggregating substations
- **DCS communication processors** bridging field networks

It focuses on industrial communication patterns often overlooked in demos:
- **Polling loops** with configurable intervals, timeouts, retries
- **Comms quality → SCADA quality flags** (GOOD/UNCERTAIN/BAD/COMM_LOSS/STALE)
- **Timestamp handling** (server timestamps, device timestamps, drift detection)
- **Queue and dispatch behavior** (decoupling ingest from downstream consumers)
- **Endpoint health tracking** (RTT monitoring, failure counting, state machines)

## Features

- **Virtual RTUs / PLC endpoints**
  Async TCP servers exposing analog/digital points over a JSON line pseudo-protocol with configurable latency, jitter, and packet loss.

- **Polling engine**
  Scheduled polls per endpoint with independent intervals, timeouts, retry logic, and per-endpoint runtime state tracking.

- **Quality model**
  Maps communications state (HEALTHY/DEGRADED/COMM_LOSS) to SCADA quality flags (GOOD/UNCERTAIN/BAD/COMM_LOSS/STALE/FORCED) based on sample age and endpoint health.

- **Timestamp normalization**
  Tracks both server timestamps (FEP time) and optional device timestamps (RTU/PLC time) with drift detection hooks.

- **Queue + dispatcher**
  Async queue with publish-subscribe pattern feeding downstream consumers (point lifecycle simulator, historian, alarm engine).

- **Diagnostics console**
  Terminal UI summarizing endpoint health, round-trip times, consecutive failures, and queue depth with ANSI color coding.

- **Web dashboard**
  FastAPI + WebSocket UI showing live endpoint health table and real-time point updates feed with sub-second latency.

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │  Virtual RTUs / PLCs                │
                    │  (endpoint_sim.py)                  │
                    │  - TCP servers on ports 9001-900N   │
                    │  - Simulate latency, jitter, drops  │
                    │  - Expose analog/digital points     │
                    └──────────────┬──────────────────────┘
                                   │
                        JSON-over-TCP (pseudo protocol)
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  Polling Engine                     │
                    │  (poller.py)                        │
                    │  - Per-endpoint poll loops          │
                    │  - Timeout + retry logic            │
                    │  - RTT tracking                     │
                    │  - Failure counting                 │
                    └──────────────┬──────────────────────┘
                                   │
                        PointValue updates (with quality)
                                   │
                    ┌──────────────▼──────────────────────┐
                    │  Quality Model                      │
                    │  (quality.py)                       │
                    │  CommsState → QualityFlag           │
                    │  - HEALTHY → GOOD                   │
                    │  - DEGRADED → UNCERTAIN             │
                    │  - COMM_LOSS → COMM_LOSS            │
                    │  - Sample age → STALE               │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  Dispatcher Queue                   │
                    │  (dispatcher.py)                    │
                    │  - Async queue (max depth: 1000)    │
                    │  - Pub/sub pattern                  │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────┴──────────────────────┐
                    │                                     │
                    ▼                                     ▼
        ┌───────────────────────┐         ┌──────────────────────────┐
        │ Diagnostics Console   │         │  Web Dashboard           │
        │ (ui/console.py)       │         │  (web/)                  │
        │ - Terminal UI         │         │  - FastAPI + WebSocket   │
        │ - Endpoint health     │         │  - Browser UI            │
        │ - RTT, failures       │         │  - Live updates          │
        └───────────────────────┘         └──────────────────────────┘
                    │
                    │ (optional integration seams)
                    │
                    ▼
        ┌──────────────────────────────────────────────┐
        │  Downstream Consumers (not in this repo)     │
        ├──────────────────────────────────────────────┤
        │  - Point lifecycle simulator                 │
        │  - Historian writer (e.g., TimescaleDB)      │
        │  - Alarm engine                              │
        │  - Trending / analytics                      │
        └──────────────────────────────────────────────┘
```

## Pseudo-protocol (no Modbus / DNP3 / OPC UA)

**IMPORTANT:** This project does **NOT** use Modbus, DNP3, OPC UA, IEC 60870-5-104, or any vendor protocol stacks.

It uses a **simple JSON line protocol** defined inside this repository for demonstration purposes only. The protocol is intentionally minimal to focus on FEP behavior (polling, quality, dispatch) rather than protocol parsing complexity.

**Poll Request (FEP → Endpoint):**
```json
{"type": "poll", "request_id": "uuid", "points": ["PT_101", "RUN_FB"]}
```

**Poll Response (Endpoint → FEP):**
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

The protocol is **newline-terminated JSON** over TCP. Each endpoint is a simple async server that:
- Accepts connections
- Reads poll requests (one per line)
- Simulates configurable latency + jitter
- Optionally drops packets to simulate unreliable networks
- Returns point values with sequence numbers and device timestamps

## Installation

### Using pip

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install pytest pytest-asyncio
pip install fastapi 'uvicorn[standard]'  # For web UI
```

### Using uv (recommended)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install from pyproject.toml
uv pip install .
uv pip install '.[dev]'  # Development dependencies (pytest)
uv pip install '.[web]'  # Web UI dependencies (fastapi, uvicorn)
```

### From pyproject.toml

If you prefer to install all dependencies at once:

```bash
uv pip install '.[dev,web]'
```

## Running the console diagnostics demo

The console demo starts virtual RTUs and displays real-time endpoint diagnostics in the terminal.

```bash
python examples/run_demo.py
```

**What it does:**
- Starts 3 virtual RTU endpoints on ports 9001-9003
  - RTU_1: Low latency, 2% packet loss (mostly HEALTHY)
  - RTU_2: Moderate latency, 5% packet loss, 500ms clock drift
  - RTU_3: High latency, 30% packet loss (frequently DEGRADED/COMM_LOSS)
- Starts the polling engine with independent poll rates per endpoint
- Displays a terminal UI refreshing every second

**What to look for:**
- **Changing RTT**: Round-trip time varies with jitter
- **Failure counts**: Consecutive failures increment when polls timeout
- **Health transitions**: Watch endpoints transition between:
  - `HEALTHY` (green) - Normal operation
  - `DEGRADED` (yellow) - Experiencing retries but still connecting
  - `COMM_LOSS` (red) - Cannot reach endpoint
- **Queue depth**: Number of point update batches waiting in dispatcher queue
- **Last fault**: Error message from most recent failure (timeout, connection refused, etc.)

Press `Ctrl+C` to exit.

## Running the web dashboard

For a browser-based real-time monitoring interface:

```bash
# Make sure web dependencies are installed
pip install fastapi 'uvicorn[standard]'

# Run web demo
python examples/run_web_demo.py
```

Then open **http://localhost:8000** in your browser.

**What it does:**
- Starts the same 3 virtual RTU endpoints as the console demo
- Starts the polling engine + dispatcher
- Starts a FastAPI server on port 8000 with WebSocket support

**Web UI features:**
- **Top summary**: Displays current dispatcher queue depth
- **Endpoint health table**: Shows for each endpoint:
  - Health status (color-coded: green/yellow/red)
  - Last poll timestamp
  - Round-trip time (RTT) in milliseconds
  - Consecutive failure count
  - Queue depth
  - Last fault message
- **Point updates feed**: Rolling list of recent point value updates showing:
  - Endpoint ID
  - Point name
  - Current value
  - Quality flag (GOOD/UNCERTAIN/STALE/COMM_LOSS/etc.)
  - Server timestamp
  - Device timestamp (from RTU/PLC)
- **Real-time updates**: WebSocket connections provide sub-second latency
- **Auto-reconnect**: If connection drops, automatically reconnects after 2 seconds

**API endpoints:**
- `GET /` - Web dashboard UI
- `GET /api/diagnostics` - Current endpoint states (JSON snapshot)
- `GET /api/points` - Recent point update history (JSON)
- `WS /ws/diagnostics` - WebSocket for real-time diagnostics
- `WS /ws/points` - WebSocket for real-time point updates

Press `Ctrl+C` to stop the server.

## How this fits with other SCADA projects

This FEP simulator provides the **communications and normalization layer** between:

1. **Upstream: PLC logic emulators**
   - IEC 61131 ladder logic simulators
   - Process simulation (tank levels, valve positions, pump states)
   - Device-level control logic

2. **Downstream: Process data consumers**
   - **Point lifecycle simulators** (value changes, state transitions)
   - **Historian / time-series databases** (InfluxDB, TimescaleDB, Cassandra)
   - **Alarm engines** (limit monitoring, alarm state machines, notification)
   - **Trending and analytics** (process optimization, ML models)

**Integration seams:**

The dispatcher provides a clean integration point via the `PointValue` model:

```python
@dataclass
class PointValue:
    definition: PointDef        # Point metadata (address, type, units)
    value: float | bool         # Current value
    quality: QualityFlag        # GOOD/UNCERTAIN/STALE/etc.
    server_ts: datetime         # FEP timestamp (UTC)
    device_ts: datetime | None  # RTU/PLC timestamp (optional)
    source: str                 # "POLL" / "MANUAL" / "SIM"
    sequence_num: int | None    # Sequence number for duplicate detection
```

**Example downstream integration:**

```python
from fep.dispatcher import Dispatcher

async def my_historian_writer(updates: list[PointValue]):
    for point in updates:
        if point.quality == QualityFlag.GOOD:
            await store_to_timeseries_db(
                point.definition.address,
                point.value,
                point.server_ts
            )

dispatcher = Dispatcher()
dispatcher.subscribe(my_historian_writer)
```

**Conceptual flow:**

```
PLC Emulator → Process Values → [This FEP] → PointValue stream → Lifecycle Sim
                                    ↓
                              Quality flags
                              Timestamps
                              Sequence numbers
                                    ↓
                              Historian / Alarms
```

The FEP adds the **operational concerns** (communications reliability, quality classification, normalization) that bridge device-level simulation and enterprise-level analytics.

## Limitations and possible extensions

### Current limitations

- **No real industrial protocols**
  This project uses a custom JSON line protocol. It does not implement Modbus TCP/RTU, DNP3, IEC 60870-5-104, OPC UA, or vendor-specific protocols.

- **No security / authentication**
  No TLS, no user authentication, no role-based access control. Suitable for demos and development only.

- **Single-process, in-memory only**
  All state (endpoint configs, point history, queue) is in-memory. No persistence, no distributed deployment, no high availability.

- **No redundancy / failover**
  Real FEPs have redundant communication paths, backup servers, and automatic failover. This demo is single-threaded.

- **Simplified quality model**
  Real SCADA systems have complex quality inheritance (source quality, communications quality, device quality, override quality). This demo uses a simplified two-level model.

### Possible extensions

**Protocol adapters:**
- Plug in a real **Modbus TCP** driver behind the polling engine interface
- Add **DNP3** support using pydnp3 or dnp3-python
- Integrate **OPC UA** client using asyncua
- Support **IEC 60870-5-104** for substation automation

**Persistence and scalability:**
- Write point updates to **TimescaleDB** or **InfluxDB** for historical trending
- Use **Redis** for shared state across multiple FEP instances
- Implement **HA / failover** with primary/standby FEP pairs

**Observability:**
- Expose metrics via **Prometheus** (poll counts, failure rates, queue depth, RTT percentiles)
- Add **structured logging** with correlation IDs for debugging
- Implement **distributed tracing** (OpenTelemetry) for multi-hop data flows

**Operator interface:**
- Add **manual point forcing** via web UI or API
- Implement **on-demand polls** (poll a specific endpoint immediately)
- Add **configuration management** (add/remove endpoints without restart)
- Support **alarm acknowledgment** workflow

**Advanced quality handling:**
- Implement **quality inheritance** (bad input → bad calculation)
- Add **manual quality override** (force GOOD for maintenance)
- Support **quality propagation** through calculations

**Integration examples:**
- Connect to a **PLC logic simulator** (OpenPLC, Beremiz) via Modbus TCP
- Feed data to a **point lifecycle simulator** for state machine execution
- Export to **Grafana** dashboards for visualization
- Integrate with **alarm notification** systems (email, SMS, Slack)

## Tests

Run the test suite to verify protocol encoding, quality classification, and polling engine behavior:

```bash
pytest tests/ -v
```

**Test coverage:**
- Protocol encoding/decoding (round-trip tests)
- Quality model classification logic (HEALTHY/DEGRADED/COMM_LOSS → quality flags)
- Polling engine integration with virtual endpoints (timeouts, retries, state updates)

All 18 tests should pass.

## Project structure

```
scada-comms-fep/
├── fep/                      # Core FEP modules
│   ├── models.py             # Data models (PointValue, QualityFlag)
│   ├── quality.py            # Quality classification logic
│   ├── timebase.py           # UTC timestamp utilities
│   ├── protocol.py           # JSON line protocol encode/decode
│   ├── endpoint_sim.py       # Virtual RTU/PLC TCP servers
│   ├── poller.py             # Polling engine with retry logic
│   └── dispatcher.py         # Async queue + pub/sub
├── ui/
│   └── console.py            # Terminal diagnostics UI
├── web/                      # Web dashboard
│   ├── state.py              # Web state manager
│   ├── server.py             # FastAPI + WebSocket server
│   └── static/               # HTML, CSS, JavaScript
│       ├── index.html
│       ├── styles.css
│       └── app.js
├── examples/
│   ├── run_demo.py           # Console demo
│   └── run_web_demo.py       # Web UI demo
├── tests/
│   ├── test_protocol.py      # Protocol tests
│   ├── test_quality.py       # Quality model tests
│   └── test_polling_loop.py  # Polling engine integration tests
├── pyproject.toml            # Project metadata + dependencies
└── README.md                 # This file
```

## License

Demonstration code for educational and portfolio purposes.

## Contact

Built as part of a SCADA systems engineering portfolio demonstrating:
- Industrial communications patterns
- Async I/O and concurrent polling
- Quality classification and normalization
- Real-time data dispatch and monitoring
