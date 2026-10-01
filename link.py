"""Chạy tiến trình Node (node/bridge.mjs) và nói chuyện với nó qua từng dòng JSON.

Không import gì từ Hermes để test được bằng một bridge giả.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

READY_TIMEOUT = 25
CALL_TIMEOUT = 30


class BridgeError(RuntimeError):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class NodeLink:
    def __init__(
        self,
        script: Path,
        args: list[str],
        on_message: Callable[[dict[str, Any]], Awaitable[None]],
        on_lost: Callable[[BridgeError], Awaitable[None]] | None = None,
        cwd: Path | None = None,
    ) -> None:
        self.script, self.args, self.cwd = script, args, cwd or script.parent
        self.on_message, self.on_lost = on_message, on_lost
        self.process: asyncio.subprocess.Process | None = None
        self.own_id = ""
        self._ready: asyncio.Future[str] | None = None
        self._waiting: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []
        self._counter = 0
        self._stopping = False
        self._fatal: BridgeError | None = None

    async def start(self, timeout: float = READY_TIMEOUT) -> str:
        self._ready = asyncio.get_running_loop().create_future()
        self.process = await asyncio.create_subprocess_exec(
            "node", str(self.script), *self.args, cwd=str(self.cwd),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            limit=1024 * 1024,
        )
        self._tasks = [
            asyncio.create_task(self._read_stdout()),
            asyncio.create_task(self._drain_stderr()),
            # Tin đến được xử lý ở hàng đợi riêng: nếu xử lý ngay trong vòng đọc stdout thì
            # lệnh gửi trả lời sẽ chờ chính vòng đọc đó và tự khoá nhau.
            asyncio.create_task(self._deliver()),
        ]
        try:
            self.own_id = await asyncio.wait_for(self._ready, timeout)
        except BaseException:
            await self.stop()
            raise
        return self.own_id

    async def call(self, op: str, timeout: float = CALL_TIMEOUT, **fields: Any) -> dict[str, Any]:
        process = self.process
        if not process or not process.stdin or process.returncode is not None:
            raise BridgeError("cầu nối Zalo chưa chạy")
        self._counter += 1
        request_id = str(self._counter)
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._waiting[request_id] = future
        try:
            process.stdin.write((json.dumps({"id": request_id, "op": op, **fields}, ensure_ascii=False) + "\n").encode("utf-8"))
            await process.stdin.drain()
            reply = await asyncio.wait_for(future, timeout)
        finally:
            self._waiting.pop(request_id, None)
        if not reply.get("ok"):
            raise BridgeError(str(reply.get("error") or "Zalo từ chối yêu cầu"))
        return reply

    async def stop(self) -> None:
        self._stopping = True
        process, self.process = self.process, None
        if process and process.returncode is None:
            with suppress(Exception):
                process.terminate()
            with suppress(Exception):
                await asyncio.wait_for(process.wait(), timeout=5)
        current = asyncio.current_task()
        for task in self._tasks:
            if task is not current:
                task.cancel()
        for task in self._tasks:
            if task is not current:
                with suppress(asyncio.CancelledError, Exception):
                    await task
        self._tasks = []

    async def _read_stdout(self) -> None:
        assert self.process and self.process.stdout
        stream = self.process.stdout
        try:
            while line := await stream.readline():
                try:
                    payload = json.loads(line.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if isinstance(payload, dict):
                    self._route(payload)
        finally:
            error = self._fatal or BridgeError("cầu nối Zalo đã dừng")
            if self._ready and not self._ready.done():
                self._ready.set_exception(error)
            for future in self._waiting.values():
                if not future.done():
                    future.set_exception(error)
            if not self._stopping and self.own_id and self.on_lost:
                asyncio.create_task(self.on_lost(error))

    def _route(self, payload: dict[str, Any]) -> None:
        kind = payload.get("t")
        if kind == "ready":
            if self._ready and not self._ready.done():
                self._ready.set_result(str(payload.get("self") or ""))
        elif kind == "reply":
            future = self._waiting.get(str(payload.get("id") or ""))
            if future and not future.done():
                future.set_result(payload)
        elif kind == "message":
            self._inbox.put_nowait(payload)
        elif kind == "fatal":
            code = payload.get("code")
            self._fatal = BridgeError(str(payload.get("error") or "lỗi không rõ"), code if isinstance(code, int) else None)
        elif kind == "status":
            logger.info("Zalo cá nhân: trạng thái kết nối %s", payload.get("state"))

    async def _deliver(self) -> None:
        while True:
            payload = await self._inbox.get()
            try:
                await self.on_message(payload)
            except Exception:
                logger.exception("Zalo cá nhân: lỗi khi xử lý tin đến")

    async def _drain_stderr(self) -> None:
        # Phải đọc hết stderr, nếu không bộ đệm đầy sẽ làm tiến trình Node đứng hình.
        assert self.process and self.process.stderr
        while line := await self.process.stderr.readline():
            logger.debug("Zalo cá nhân (node): %s", line.decode("utf-8", "replace").rstrip()[:300])
