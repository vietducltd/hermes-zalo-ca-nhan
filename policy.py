"""Luật trả lời của bot: ai được trả lời, khi nào nhường cho người thật.

Module này cố ý không import gì từ Hermes để test chạy được bằng Python thường.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

TEXT_LIMIT = 1800
DEFAULT_PAUSE_SECONDS = 24 * 60 * 60
HANDOFF_TAG = "[[CHUYEN_NGUOI]]"
EVERYONE = "*"

RESUME_PHRASES = ("trợ lý trả lời tiếp", "bot trả lời tiếp")

# Khách nhắc tới các cụm này thì bot dừng và báo đã chuyển người phụ trách.
HANDOFF_KEYWORDS = (
    "khiếu nại", "hoàn tiền", "thanh toán", "chuyển khoản",
    "người thật", "gặp nhân viên", "tư vấn viên",
    "mật khẩu", "otp", "mã pin", "số thẻ", "thẻ tín dụng", "thẻ ngân hàng",
)

DEFAULT_REPLIES = {
    "handoff": "Em đã chuyển cho người phụ trách hỗ trợ trực tiếp. Anh/chị nhắn thêm chi tiết tại đây nhé.",
    "media": "Em đã nhận được nội dung và chuyển cho người phụ trách xem giúp anh/chị nhé.",
    "resume": "Em quay lại hỗ trợ rồi ạ. Anh/chị cần hỏi gì thêm không?",
}


def tidy(text: str) -> str:
    """Chữ thường, gộp khoảng trắng, chuẩn hoá dấu về dạng dựng sẵn (NFC)."""
    return " ".join(unicodedata.normalize("NFC", text or "").lower().split())


def _base(char: str) -> str:
    if char == "đ":
        return "d"
    return unicodedata.normalize("NFD", char)[0]


def fold(text: str) -> str:
    """Bỏ dấu tiếng Việt, giữ nguyên số ký tự để đối chiếu vị trí với bản có dấu."""
    return "".join(_base(char) for char in tidy(text))


def _typed_as(span: str, keyword: str) -> bool:
    # Mỗi ký tự khách gõ phải đúng dấu hoặc không dấu; sai dấu ("thế" so với "thẻ") là từ khác.
    return all(a == b or a == _base(b) for a, b in zip(span, keyword))


def contains_phrase(text: str, phrase: str) -> bool:
    """Tìm cụm từ nguyên vẹn (không dính vào từ khác), chấp nhận khách gõ không dấu."""
    plain, keyword = tidy(text), tidy(phrase)
    if not keyword:
        return False
    pattern = rf"(?<!\w){re.escape(fold(keyword))}(?!\w)"
    return any(
        _typed_as(plain[match.start():match.end()], keyword)
        for match in re.finditer(pattern, fold(plain))
    )


def wants_human(text: str, extra_keywords: Iterable[str] = ()) -> bool:
    return any(contains_phrase(text, keyword) for keyword in (*HANDOFF_KEYWORDS, *extra_keywords))


def is_resume(text: str) -> bool:
    return fold(text).strip(" .!") in {fold(phrase) for phrase in RESUME_PHRASES}


def mask_id(value: str) -> str:
    """Mã băm ngắn để ghi log mà không lộ ID Zalo thật."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:10]


def chunk_text(text: str, limit: int = TEXT_LIMIT) -> list[str]:
    """Cắt câu trả lời dài thành nhiều tin, ưu tiên cắt ở chỗ xuống dòng rồi tới khoảng trắng."""
    rest = (text or "").strip()
    chunks: list[str] = []
    while len(rest) > limit:
        cut = rest.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        chunks.append(rest)
    return chunks


@dataclass(frozen=True)
class GroupRule:
    enabled: bool = True
    require_mention: bool = True


@dataclass(frozen=True)
class Settings:
    """Phần `extra` trong config.yaml. Danh sách rỗng nghĩa là chặn hết, không phải cho hết."""

    allowed_users: frozenset[str] = frozenset()
    groups: Mapping[str, GroupRule] = field(default_factory=dict)
    pause_seconds: int = DEFAULT_PAUSE_SECONDS
    owner_takeover: bool = True
    extra_keywords: tuple[str, ...] = ()
    replies: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_REPLIES))

    @classmethod
    def from_extra(cls, extra: Mapping[str, Any] | None) -> "Settings":
        extra = dict(extra or {})
        mention_default = bool(extra.get("require_mention", True))
        replies = dict(DEFAULT_REPLIES)
        for key in replies:
            custom = str(extra.get(f"{key}_message") or "").strip()
            if custom:
                replies[key] = custom
        try:
            pause_seconds = max(60, int(extra.get("handoff_seconds", DEFAULT_PAUSE_SECONDS)))
        except (TypeError, ValueError):
            pause_seconds = DEFAULT_PAUSE_SECONDS
        return cls(
            # ID Zalo toàn số nên YAML dễ đọc thành số nếu quên ngoặc kép; luôn ép về chuỗi.
            allowed_users=frozenset(str(item).strip() for item in _as_list(extra.get("allowed_users"))),
            groups=_group_rules(extra.get("allowed_groups"), mention_default),
            pause_seconds=pause_seconds,
            owner_takeover=bool(extra.get("owner_takeover", True)),
            extra_keywords=tuple(str(item) for item in _as_list(extra.get("handoff_keywords"))),
            replies=replies,
        )

    def allows(self, *, kind: str, thread_id: str, sender_id: str, mentions: Iterable[str], own_id: str) -> bool:
        if kind != "group":
            return str(sender_id) in self.allowed_users
        rule = self.groups.get(str(thread_id))
        if rule is None or not rule.enabled:
            return False
        return not rule.require_mention or (bool(own_id) and str(own_id) in {str(item) for item in mentions})


def _as_list(value: Any) -> list:
    if value is None or value == "":
        return []
    return list(value) if isinstance(value, (list, tuple, set, frozenset)) else [value]


def _group_rules(raw: Any, mention_default: bool) -> dict[str, GroupRule]:
    if isinstance(raw, Mapping):
        items = raw.items()
    else:
        items = ((group_id, True) for group_id in _as_list(raw))
    rules: dict[str, GroupRule] = {}
    for group_id, value in items:
        if isinstance(value, Mapping):
            rule = GroupRule(bool(value.get("enabled", False)), bool(value.get("require_mention", mention_default)))
        else:
            rule = GroupRule(bool(value), mention_default)
        rules[str(group_id).strip()] = rule
    return rules
