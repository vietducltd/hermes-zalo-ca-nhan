"""Test luồng xử lý tin của adapter. Cần chạy bằng Python của Hermes (có module `gateway`)."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "zalo_ca_nhan_plugin"

try:
    import gateway.platforms.base  # noqa: F401
except ImportError:
    HERMES = False
else:
    HERMES = True


def load_plugin():
    if PACKAGE not in sys.modules:
        spec = importlib.util.spec_from_file_location(PACKAGE, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[PACKAGE] = module
        spec.loader.exec_module(module)
    return sys.modules[f"{PACKAGE}.adapter"], sys.modules[f"{PACKAGE}.policy"], sys.modules[f"{PACKAGE}.store"]


class FakeLink:
    def __init__(self):
        self.sent: list[dict] = []

    async def call(self, op, **fields):
        self.sent.append({"op": op, **fields})
        return {"ok": True, "msgId": f"bot-{len(self.sent)}"}

    async def stop(self):
        return None


@unittest.skipUnless(HERMES, "cần Python của Hermes")
class AdapterFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        adapter_module, policy, store = load_plugin()
        self.policy = policy
        self.folder = tempfile.TemporaryDirectory()
        self.adapter = adapter_module.ZaloCaNhanAdapter.__new__(adapter_module.ZaloCaNhanAdapter)
        self.adapter.settings = policy.Settings.from_extra({
            "allowed_users": ["khach"],
            "allowed_groups": {"nhom": {"enabled": True, "require_mention": True}},
        })
        self.adapter.db = store.StateDB(Path(self.folder.name) / "state.sqlite3")
        self.adapter.link = FakeLink()
        self.adapter.own_id = "bot"
        self.adapter._kinds = {}
        self.adapter._askers = {}
        self.forwarded: list = []

        async def handle_message(event):
            self.forwarded.append(event)

        self.adapter.handle_message = handle_message
        self.adapter.build_source = lambda **fields: fields
        self.counter = 0

    def tearDown(self):
        self.adapter.db.close()
        self.folder.cleanup()

    def dm(self, text, sender="khach", **extra):
        self.counter += 1
        return {"t": "message", "threadId": sender, "kind": "user", "senderId": sender, "senderName": "Khách",
                "msgId": f"in-{self.counter}", "text": text, "self": False, "mentions": [], **extra}

    def group(self, text, mentions=(), thread="nhom", sender="tv1"):
        return {**self.dm(text, sender=sender), "threadId": thread, "kind": "group", "mentions": list(mentions)}

    def own(self, text, thread, by_bot, kind="user", **extra):
        """Bản sao tin do chính tài khoản bot gửi đi (bot gửi hoặc chủ tài khoản gõ tay)."""
        return {**self.dm(text, sender="bot"), "threadId": thread, "kind": kind, "self": True, "byBot": by_bot, **extra}

    @property
    def sent_texts(self):
        return [item["text"] for item in self.adapter.link.sent]

    async def test_allowed_dm_is_forwarded_once(self):
        event = self.dm("Khoá học theo lộ trình nào ạ?")
        await self.adapter._on_message(event)
        await self.adapter._on_message(event)
        self.assertEqual([item.text for item in self.forwarded], ["Khoá học theo lộ trình nào ạ?"])
        self.assertEqual(self.forwarded[0].source["chat_type"], "dm")
        self.assertEqual(self.sent_texts, [])

    async def test_stranger_is_ignored_but_listed_in_contacts(self):
        await self.adapter._on_message(self.dm("alo", sender="la"))
        self.assertEqual(self.forwarded, [])
        self.assertEqual(self.sent_texts, [])
        self.assertEqual(self.adapter.db.contacts()[0][2], "la")

    async def test_group_needs_mention(self):
        await self.adapter._on_message(self.group("giá bao nhiêu"))
        await self.adapter._on_message(self.group("@Bot giá bao nhiêu", mentions=["bot"]))
        await self.adapter._on_message(self.group("@Bot alo", mentions=["bot"], thread="nhom-la"))
        self.assertEqual([item.text for item in self.forwarded], ["@Bot giá bao nhiêu"])
        self.assertEqual(self.forwarded[0].source["chat_type"], "group")

    async def test_keyword_hands_off_then_customer_resumes(self):
        replies = self.adapter.settings.replies
        await self.adapter._on_message(self.dm("Tôi muốn hoàn tiền"))
        await self.adapter._on_message(self.dm("alo còn đó không"))
        self.assertEqual(self.forwarded, [])
        self.assertEqual(self.sent_texts, [replies["handoff"]])
        await self.adapter._on_message(self.dm("trợ lý trả lời tiếp"))
        await self.adapter._on_message(self.dm("cho hỏi lịch học"))
        self.assertEqual(self.sent_texts, [replies["handoff"], replies["resume"]])
        self.assertEqual([item.text for item in self.forwarded], ["cho hỏi lịch học"])

    async def test_media_pauses_dm_but_is_silent_in_group(self):
        await self.adapter._on_message(self.dm(None))
        await self.adapter._on_message(self.dm(None))
        self.assertEqual(self.sent_texts, [self.adapter.settings.replies["media"]])
        self.assertTrue(self.adapter.db.is_paused("khach", "khach"))
        await self.adapter._on_message(self.group(None, mentions=["bot"]))
        self.assertEqual(len(self.sent_texts), 1)
        self.assertFalse(self.adapter.db.is_paused("nhom", "tv1"))

    async def test_owner_typing_takes_over_dm_only(self):
        await self.adapter._on_message(self.own("bot tự gửi", "khach", by_bot=True))
        self.assertFalse(self.adapter.db.is_paused("khach", "khach"))
        await self.adapter._on_message(self.own("chủ chat trong nhóm", "nhom", by_bot=False, kind="group"))
        self.assertFalse(self.adapter.db.is_paused("nhom", "tv1"))
        await self.adapter._on_message(self.own("để anh tư vấn", "khach", by_bot=False))
        self.assertTrue(self.adapter.db.is_paused("khach", "khach"))
        await self.adapter._on_message(self.dm("dạ vâng"))
        self.assertEqual(self.forwarded, [])

    async def test_bot_reply_recorded_in_db_is_not_a_takeover(self):
        result = await self.adapter.send("khach", "Dạ em chào anh")
        await self.adapter._on_message(self.own("Dạ em chào anh", "khach", by_bot=False, msgId=result.message_id))
        self.assertFalse(self.adapter.db.is_paused("khach", "khach"))

    async def test_send_strips_tag_and_pauses_the_asker(self):
        await self.adapter._on_message(self.group("@Bot cho gặp quản lý", mentions=["bot"]))
        result = await self.adapter.send("nhom", f"Dạ em đã báo quản lý ạ. {self.policy.HANDOFF_TAG}")
        self.assertTrue(result.success)
        self.assertEqual(self.adapter.link.sent[-1], {"op": "send", "threadId": "nhom", "kind": "group", "text": "Dạ em đã báo quản lý ạ."})
        self.assertTrue(self.adapter.db.is_paused("nhom", "tv1"))
        self.assertFalse(self.adapter.db.is_paused("nhom", "tv2"))

    async def test_send_tag_only_uses_fixed_reply_and_long_text_is_chunked(self):
        await self.adapter.send("khach", self.policy.HANDOFF_TAG)
        self.assertEqual(self.sent_texts, [self.adapter.settings.replies["handoff"]])
        result = await self.adapter.send("khach", "xin chào " * 500)
        self.assertEqual(len(self.sent_texts), 1 + 3)
        self.assertEqual(result.message_id, "bot-4")
        self.assertTrue((await self.adapter.send("khach", "  ")).success)
        self.assertEqual(len(self.sent_texts), 4)

    async def test_send_fails_cleanly_when_not_connected(self):
        self.adapter.link = None
        self.assertFalse((await self.adapter.send("khach", "chào")).success)


if __name__ == "__main__":
    unittest.main()
