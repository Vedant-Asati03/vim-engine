"""Async log streaming utility for the Textual adapter demo."""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import suppress
from datetime import datetime
from typing import Deque, Set


class NetworkLogStreamer:
    """Broadcasts log lines to TCP clients (e.g., via ``nc``)."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        *,
        history: int = 200,
        queue_size: int = 1024,
    ) -> None:
        self.host = host
        self.port = port
        self._history: Deque[str] = deque(maxlen=history)
        self._queue_size = queue_size
        self._queue: asyncio.Queue[str] | None = None
        self._server: asyncio.AbstractServer | None = None
        self._pump_task: asyncio.Task[None] | None = None
        self._clients: Set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        """Start listening for TCP clients."""

        if self._server is not None:
            return
        self._queue = asyncio.Queue(maxsize=self._queue_size)
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        sockets = self._server.sockets or []
        if sockets:
            self.port = sockets[0].getsockname()[1]
        self._pump_task = asyncio.create_task(self._pump())

    async def stop(self) -> None:
        """Stop listening and close all client connections."""

        if self._pump_task:
            self._pump_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._pump_task
            self._pump_task = None
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        await self._close_all_clients()
        self._queue = None

    def log(self, line: str) -> None:
        """Queue a line to broadcast to all connected clients."""

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = f"{timestamp} | {line}\n"
        self._history.append(entry)
        if self._queue is None:
            return
        try:
            self._queue.put_nowait(entry)
        except asyncio.QueueFull:
            pass

    async def _pump(self) -> None:
        assert self._queue is not None
        while True:
            entry = await self._queue.get()
            await self._broadcast(entry)

    async def _broadcast(self, entry: str) -> None:
        dead: list[asyncio.StreamWriter] = []
        for writer in self._clients.copy():
            try:
                writer.write(entry.encode("utf-8"))
                await writer.drain()
            except Exception:
                dead.append(writer)
        for writer in dead:
            await self._close_writer(writer)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._clients.add(writer)
        try:
            for entry in self._history:
                writer.write(entry.encode("utf-8"))
            await writer.drain()
            while True:
                chunk = await reader.read(1024)
                if not chunk:
                    break
        finally:
            await self._close_writer(writer)

    async def _close_writer(self, writer: asyncio.StreamWriter) -> None:
        if writer in self._clients:
            self._clients.remove(writer)
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()

    async def _close_all_clients(self) -> None:
        for writer in list(self._clients):
            await self._close_writer(writer)


__all__ = ["NetworkLogStreamer"]
