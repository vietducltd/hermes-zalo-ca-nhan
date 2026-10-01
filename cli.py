"""Lệnh dòng lệnh: hermes -p <profile> zalo-ca-nhan <lệnh>."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from contextlib import suppress

from .adapter import install_node_deps
from .paths import BRIDGE_SCRIPT, PLUGIN_DIR, deps_installed, qr_file, session_file, state_file
from .store import StateDB

COMMAND = "zalo-ca-nhan"


def register_cli(parser: argparse.ArgumentParser) -> None:
    subs = parser.add_subparsers(dest="zalo_command")
    subs.add_parser("setup", help="Cài thư viện Node mà plugin cần (chạy một lần sau khi cài plugin)")
    subs.add_parser("login", help="Đăng nhập Zalo bằng mã QR, lưu phiên vào profile này")
    subs.add_parser("status", help="Kiểm tra Node, thư viện và phiên đăng nhập")
    subs.add_parser("groups", help="Liệt kê nhóm của tài khoản kèm Group ID (chỉ đọc)")
    find = subs.add_parser("find-group", help="Lấy Group ID từ link mời zalo.me/g/... (chỉ đọc)")
    find.add_argument("link", help="Link mời nhóm Zalo")
    subs.add_parser("friends", help="Liệt kê bạn bè kèm User ID (chỉ đọc)")
    subs.add_parser("contacts", help="Xem người và nhóm đã nhắn tới bot kể từ khi gateway chạy")
    logout = subs.add_parser("logout", help="Xoá phiên Zalo đã lưu trong profile này")
    logout.add_argument("--yes", action="store_true", help="Xác nhận xoá phiên")
    parser.set_defaults(func=run)


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _setup() -> int:
    if not shutil.which("node") or not shutil.which("npm"):
        return _fail("Chưa có Node.js. Cài Node.js 18 trở lên tại https://nodejs.org rồi chạy lại.")
    code = install_node_deps(capture=False).returncode
    if code == 0:
        print("Đã cài xong thư viện. Bước tiếp theo: login")
    return code


def _bridge(mode: str, *args: str) -> list[str]:
    return ["node", str(BRIDGE_SCRIPT), mode, "--session", str(session_file()), *args]


def _ask(mode: str, *args: str) -> dict | None:
    """Chạy bridge một lần ở chế độ chỉ đọc và trả về gói JSON cuối cùng."""
    if not session_file().exists():
        _fail(f"Chưa đăng nhập Zalo. Chạy: hermes -p <profile> {COMMAND} login")
        return None
    if not deps_installed():
        _fail(f"Chưa cài thư viện. Chạy: hermes -p <profile> {COMMAND} setup")
        return None
    result = subprocess.run(_bridge(mode, *args), cwd=PLUGIN_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    payload: dict = {}
    for line in result.stdout.splitlines():
        with suppress(json.JSONDecodeError):
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                payload = parsed
    if result.returncode != 0 or payload.get("t") == "fatal":
        _fail(str(payload.get("error") or result.stderr.strip()[-300:] or "Không đọc được thông tin từ Zalo."))
        return None
    return payload


def _open_file(path) -> None:
    with suppress(Exception):
        if os.name == "nt":
            os.startfile(path)  # noqa: S606 - mở ảnh QR bằng trình xem ảnh mặc định
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def _login() -> int:
    if not deps_installed() and _setup() != 0:
        return 1
    session_file().parent.mkdir(parents=True, exist_ok=True)
    qr_file().unlink(missing_ok=True)
    process = subprocess.Popen(
        _bridge("login", "--qr", str(qr_file())), cwd=PLUGIN_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
    )
    error = ""
    assert process.stdout is not None
    for line in process.stdout:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("t") if isinstance(event, dict) else None
        if kind == "qr":
            print(f"Mở Zalo trên điện thoại > biểu tượng QR > quét mã tại: {qr_file()}")
            _open_file(qr_file())
        elif kind == "scanned":
            print(f"Đã quét ({event.get('name') or 'tài khoản Zalo'}). Bấm xác nhận đăng nhập trên điện thoại.")
        elif kind == "expired":
            print("Mã QR hết hạn, đang tạo mã mới...")
        elif kind == "declined":
            error = "Bạn đã từ chối đăng nhập trên điện thoại."
        elif kind == "fatal":
            error = str(event.get("error") or "")
        elif kind == "logged_in":
            print("Đăng nhập Zalo thành công. Phiên chỉ lưu trong profile này.")
    stderr = process.stderr.read() if process.stderr else ""
    process.wait()
    qr_file().unlink(missing_ok=True)
    if process.returncode != 0 or not session_file().exists():
        return _fail(f"Đăng nhập Zalo thất bại. {error or stderr.strip()[-300:]}")
    return 0


def _status() -> int:
    node = shutil.which("node")
    version = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip() if node else ""
    print(f"Node.js       : {version or 'chưa cài'}")
    print(f"Thư viện Zalo : {'đã cài' if deps_installed() else 'chưa cài (chạy setup)'}")
    print(f"Phiên Zalo    : {'đã đăng nhập' if session_file().exists() else 'chưa đăng nhập (chạy login)'}")
    return 0 if node and deps_installed() and session_file().exists() else 1


def _table(headers: tuple[str, ...], rows: list[tuple]) -> None:
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)]
    for row in (headers, *rows):
        print("  ".join(str(cell).ljust(width) for cell, width in zip(row, widths)).rstrip())


def _groups() -> int:
    payload = _ask("groups")
    if payload is None:
        return 1
    items = payload.get("items") or []
    if not items:
        print("Tài khoản này chưa ở trong nhóm nào.")
        return 0
    _table(("Group ID", "Thành viên", "Tên nhóm"), [(item.get("id"), item.get("members"), item.get("name")) for item in items])
    return 0


def _find_group(link: str) -> int:
    payload = _ask("group", "--link", link)
    if payload is None:
        return 1
    item = payload.get("item") or {}
    _table(("Group ID", "Thành viên", "Tên nhóm"), [(item.get("id"), item.get("members"), item.get("name"))])
    return 0


def _friends() -> int:
    payload = _ask("friends")
    if payload is None:
        return 1
    print(f"User ID của chính tài khoản bot: {payload.get('self')}")
    items = payload.get("items") or []
    if items:
        _table(("User ID", "Tên"), [(item.get("id"), item.get("name")) for item in items])
    else:
        print("Tài khoản này chưa có bạn bè nào.")
    return 0


def _contacts() -> int:
    if not state_file().exists():
        print("Chưa có dữ liệu. Chạy gateway rồi nhờ một tài khoản khác nhắn cho bot.")
        return 0
    db = StateDB(state_file())
    rows = db.contacts()
    db.close()
    if not rows:
        print("Chưa có ai nhắn tới bot.")
        return 0
    _table(
        ("Loại", "ID hội thoại", "User ID", "Tên"),
        [("nhóm" if kind == "group" else "cá nhân", thread_id, user_id, name) for thread_id, kind, user_id, name, _ in rows],
    )
    return 0


def _logout(confirmed: bool) -> int:
    if not confirmed:
        print("Chưa xoá gì. Chạy lại kèm --yes để xác nhận.")
        return 2
    session_file().unlink(missing_ok=True)
    qr_file().unlink(missing_ok=True)
    print("Đã xoá phiên Zalo khỏi profile này.")
    return 0


def run(args: argparse.Namespace) -> int:
    for stream in (sys.stdout, sys.stderr):
        with suppress(Exception):
            stream.reconfigure(errors="replace")
    command = getattr(args, "zalo_command", None) or "status"
    if command == "setup":
        return _setup()
    if command == "login":
        return _login()
    if command == "groups":
        return _groups()
    if command == "find-group":
        return _find_group(args.link)
    if command == "friends":
        return _friends()
    if command == "contacts":
        return _contacts()
    if command == "logout":
        return _logout(bool(args.yes))
    return _status()
