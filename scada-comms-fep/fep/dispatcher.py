"""
Update dispatcher with async queue and publish-subscribe pattern.

Decouples point ingestion from downstream consumers (lifecycle sim, historian, alarms).
"""

import asyncio
from typing import List, Callable, Awaitable

from .models import PointValue


class Dispatcher:
    """
    Asynchronous point update dispatcher.

    Provides a queue-based decoupling layer between the polling engine
    and downstream consumers like historians, lifecycle simulators, and alarm engines.
    """

    def __init__(self, max_queue: int = 1000) -> None:
        self._queue: asyncio.Queue[List[PointValue]] = asyncio.Queue(
            maxsize=max_queue
        )
        self._subscribers: list[Callable[[List[PointValue]], Awaitable[None]]] = []
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    @property
    def queue_depth(self) -> int:
        """Current number of batches waiting in the queue."""
        return self._queue.qsize()

    def subscribe(
        self, handler: Callable[[List[PointValue]], Awaitable[None]]
    ) -> None:
        """
        Subscribe to point updates.

        Args:
            handler: Async callback that receives batches of PointValue updates
        """
        self._subscribers.append(handler)

    async def publish(self, updates: List[PointValue]) -> None:
        """
        Publish a batch of point updates to the queue.

        Args:
            updates: List of PointValue objects to dispatch
        """
        await self._queue.put(updates)

    async def start(self) -> None:
        """Start the dispatcher task."""
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the dispatcher task."""
        self._stopped.set()
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _run(self) -> None:
        """Main dispatcher loop that fans out updates to subscribers."""
        while not self._stopped.is_set():
            try:
                updates = await asyncio.wait_for(self._queue.get(), timeout=0.1)

                # Fan out to all subscribers
                for handler in self._subscribers:
                    try:
                        await handler(updates)
                    except Exception as e:
                        # Log but don't crash if a subscriber fails
                        print(f"Dispatcher subscriber error: {e}")
            except asyncio.TimeoutError:
                # No updates, continue
                continue

    # Integration hooks for downstream systems
    def attach_point_lifecycle(
        self, handler: Callable[[List[PointValue]], Awaitable[None]]
    ) -> None:
        """
        Attach point lifecycle simulator.

        This is a semantic convenience method for clarity in system topology.
        """
        self.subscribe(handler)

    def attach_historian(
        self, handler: Callable[[List[PointValue]], Awaitable[None]]
    ) -> None:
        """
        Attach historian for time-series storage.

        This is a semantic convenience method for clarity in system topology.
        """
        self.subscribe(handler)

    def attach_alarm_engine(
        self, handler: Callable[[List[PointValue]], Awaitable[None]]
    ) -> None:
        """
        Attach alarm engine for limit monitoring.

        This is a semantic convenience method for clarity in system topology.
        """
        self.subscribe(handler)
