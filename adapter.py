"""Adapter Hermes cho một tài khoản Zalo cá nhân đăng nhập bằng QR."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from typing import Any, Optional

from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, SendResult

from .link import BridgeError, NodeLink
from .paths import BRIDGE_SCRIPT, PLATFORM, PLUGIN_DIR, deps_installed, session_file, state_file
from .policy import EVERYONE, HANDOFF_TAG, TEXT_LIMIT, Settings, chunk_text, is_resume, mask_id, wants_human
from .store import StateDB

logger = logging.getLogger(__name__)

# Zalo báo các mã này khi tài khoản mở phiên nghe ở nơi khác; tự nối lại chỉ làm hai bên giành nhau.
TAKEN_OVER_CODES = {3000, 3003}


def install_node_deps(capture: bool = True) -> subprocess.CompletedProcess:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    return subprocess.run(
        [npm, "ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=PLUGIN_DIR, capture_output=capture, text=True, encoding="utf-8", errors="replace", timeout=300,
    )


class ZaloCaNhanAdapter(BasePlatformAdapter):
    def __init__(self, config: Any) -> None:
        super().__init__(config=config, platform=Platform(PLATFORM))
        self.settings = Settings.from_extra(getattr(config, "extra", None))
        self.db: StateDB | None = None
        self.link: NodeLink | None = None
        self.own_id = ""
        self._kinds: dict[str, str] = {}
        self._askers: dict[str, str] = {}

    @property
    def enforces_own_access_policy(self) -> bool:
        """Danh sách cho phép (DM và nhóm) được kiểm tra ngay tại đây, trước khi tin tới Hermes."""
        return True

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if not session_file().exists():
            self._set_fatal_error("chua_dang_nhap", "Chưa đăng nhập Zalo. Chạy: hermes -p <profile> zalo-ca-nhan login", retryable=False)
            return False
        if not shutil.which("node"):
            self._set_fatal_error("thieu_node", "Chưa cài Node.js 18 trở lên.", retryable=False)
            return False
        if not deps_installed():
            result = await asyncio.to_thread(install_node_deps)
            if result.returncode != 0 or not deps_installed():
                logger.warning("Zalo cá nhân: cài thư viện Node thất bại: %s", (result.stderr or "")[-300:])
                self._set_fatal_error("thieu_thu_vien", "Chưa cài được zca-js. Chạy: hermes -p <profile> zalo-ca-nhan setup", retryable=False)
                return False
        self.db = StateDB(state_file())
        self.link = NodeLink(BRIDGE_SCRIPT, ["serve", "--session", str(session_file())], self._on_message, self._on_lost, cwd=PLUGIN_DIR)
        try:
            self.own_id = await self.link.start()
        except Exception as exc:
            await self._close()
            self._set_fatal_error("khong_ket_noi_duoc", f"Không kết nối được Zalo cá nhân: {exc or type(exc).__name__}", retryable=True)
            return False
        self._mark_connected()
        logger.info("Zalo cá nhân: đã kết nối tài khoản %s", mask_id(self.own_id))
        return True

    async def disconnect(self) -> None:
        self._mark_disconnected()
        await self._close()

    async def _close(self) -> None:
        link, self.link = self.link, None
        if link:
            await link.stop()
        db, self.db = self.db, None
        if db:
            db.close()

    async def _on_lost(self, error: BridgeError) -> None:
        if not self.is_connected:
            return
        taken_over = error.code in TAKEN_OVER_CODES
        message = (
            "Tài khoản Zalo vừa mở phiên nghe ở nơi khác (Zalo Web hoặc một bot khác). Tắt bên kia rồi khởi động lại gateway."
            if taken_over else f"Mất kết nối Zalo: {error}"
        )
        logger.warning("Zalo cá nhân: %s", message)
        self._set_fatal_error("mat_ket_noi", message, retryable=not taken_over)
        await self._notify_fatal_error()

    async def send(
        self, chat_id: str, content: str, reply_to: Optional[str] = None, metadata: Optional[dict[str, Any]] = None,
    ) -> SendResult:
        if not self.link or not self.db:
            return SendResult(success=False, error="Zalo cá nhân chưa kết nối")
        chat_id = str(chat_id)
        handoff = HANDOFF_TAG in (content or "")
        visible = (content or "").replace(HANDOFF_TAG, "").strip()
        if handoff:
            self.db.pause(chat_id, self._askers.get(chat_id, EVERYONE), self.settings.pause_seconds)
            visible = visible or self.settings.replies["handoff"]
        last_id = ""
        try:
            for chunk in chunk_text(visible):
                last_id = await self._send_text(chat_id, chunk) or last_id
        except Exception as exc:
            logger.warning("Zalo cá nhân: gửi thất bại tới %s: %s", mask_id(chat_id), exc)
            return SendResult(success=False, error="Không gửi được tin qua Zalo")
        return SendResult(success=True, message_id=last_id or None)

    async def send_typing(self, chat_id: str, metadata: Optional[dict[str, Any]] = None) -> None:
        return None

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        return {"chat_id": chat_id, "name": chat_id, "type": "group" if self._kind_of(str(chat_id)) == "group" else "dm"}

    def _kind_of(self, thread_id: str) -> str:
        if thread_id in self._kinds:
            return self._kinds[thread_id]
        if thread_id in self.settings.groups:
            return "group"
        return (self.db.kind_of(thread_id) if self.db else None) or "user"

    async def _send_text(self, thread_id: str, text: str) -> str:
        assert self.link and self.db
        reply = await self.link.call("send", threadId=thread_id, kind=self._kind_of(thread_id), text=text)
        msg_id = str(reply.get("msgId") or "")
        self.db.mark_sent(msg_id)
        return msg_id

    async def _say(self, thread_id: str, reply_key: str) -> None:
        try:
            await self._send_text(thread_id, self.settings.replies[reply_key])
        except Exception as exc:
            logger.warning("Zalo cá nhân: không gửi được câu trả lời cố định tới %s: %s", mask_id(thread_id), exc)

    async def _on_message(self, event: dict[str, Any]) -> None:
        db = self.db
        if db is None:
            return
        thread_id, kind = str(event.get("threadId") or ""), str(event.get("kind") or "user")
        sender_id, msg_id = str(event.get("senderId") or ""), str(event.get("msgId") or "")
        if not thread_id:
            return
        self._kinds[thread_id] = kind

        if event.get("self"):
            # Chủ tài khoản tự gõ tay cho khách thì bot nhường; trong nhóm chủ chat là chuyện thường nên bỏ qua.
            manual = not event.get("byBot") and not db.was_sent(msg_id)
            if manual and kind != "group" and self.settings.owner_takeover and db.first_time(msg_id):
                db.pause(thread_id, EVERYONE, self.settings.pause_seconds)
                logger.info("Zalo cá nhân: chủ tài khoản tiếp quản hội thoại %s", mask_id(thread_id))
            return

        if not sender_id or not db.first_time(msg_id):
            return
        db.remember_contact(thread_id, kind, sender_id, str(event.get("senderName") or ""))
        if not self.settings.allows(
            kind=kind, thread_id=thread_id, sender_id=sender_id, mentions=event.get("mentions") or [], own_id=self.own_id,
        ):
            logger.info("Zalo cá nhân: bỏ qua tin ngoài danh sách cho phép (người gửi %s, hội thoại %s)", mask_id(sender_id), mask_id(thread_id))
            return

        text = event.get("text")
        text = text.strip() if isinstance(text, str) else None
        if text and is_resume(text):
            db.resume(thread_id, sender_id)
            await self._say(thread_id, "resume")
            return
        if db.is_paused(thread_id, sender_id):
            return
        if text is None:
            # Ảnh, file, voice, sticker: bot không đọc được. Trong nhóm thì im lặng để không làm phiền.
            if kind != "group":
                db.pause(thread_id, sender_id, self.settings.pause_seconds)
                await self._say(thread_id, "media")
            return
        if not text:
            return
        if wants_human(text, self.settings.extra_keywords):
            db.pause(thread_id, sender_id, self.settings.pause_seconds)
            await self._say(thread_id, "handoff")
            return

        self._askers[thread_id] = sender_id
        name = str(event.get("senderName") or sender_id)
        source = self.build_source(
            chat_id=thread_id, chat_name=thread_id, chat_type="group" if kind == "group" else "dm",
            user_id=sender_id, user_name=name,
        )
        await self.handle_message(
            MessageEvent(text=text, message_type=MessageType.TEXT, source=source, raw_message=event, message_id=msg_id or None)
        )


def check_requirements() -> bool:
    return shutil.which("node") is not None


def has_session(config: Any) -> bool:
    return session_file().exists()


def register(ctx: Any) -> None:
    ctx.register_platform(
        name=PLATFORM,
        label="Zalo cá nhân",
        adapter_factory=lambda config: ZaloCaNhanAdapter(config),
        check_fn=check_requirements,
        validate_config=has_session,
        is_connected=has_session,
        install_hint="Cài Node.js 18+ rồi chạy: hermes -p <profile> zalo-ca-nhan setup",
        max_message_length=TEXT_LIMIT,
        emoji="💬",
        pii_safe=True,
        allow_update_command=False,
        platform_hint="Bạn đang trả lời khách qua Zalo. Viết ngắn gọn bằng tiếng Việt, chữ thuần, không dùng Markdown.",
    )
