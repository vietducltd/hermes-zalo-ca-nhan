import asyncio
import shutil
import unittest
from pathlib import Path

from link import BridgeError, NodeLink

FAKE = Path(__file__).parent / "fake_bridge.mjs"


@unittest.skipUnless(shutil.which("node"), "cần Node.js")
class NodeLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_ready_send_and_stop(self):
        async def ignore(_message):
            return None

        link = NodeLink(FAKE, ["serve"], ignore)
        self.assertEqual(await link.start(), "bot-1")
        self.assertEqual((await link.call("send", threadId="u1", kind="user", text="chào"))["msgId"], "sent-1")
        with self.assertRaises(BridgeError):
            await link.call("khong-co")
        await link.stop()
        with self.assertRaises(BridgeError):
            await link.call("send", threadId="u1", kind="user", text="chào")

    async def test_handler_can_reply_without_deadlock(self):
        got: list[tuple[str, str]] = []
        done = asyncio.Event()

        async def answer(message):
            reply = await link.call("send", timeout=5, threadId=message["threadId"], kind="user", text="đã nhận")
            got.append((message["text"], reply["msgId"]))
            done.set()

        link = NodeLink(FAKE, ["serve"], answer)
        await link.start()
        await link.call("poke", text="xin chào")
        await asyncio.wait_for(done.wait(), timeout=5)
        await link.stop()
        self.assertEqual(got, [("xin chào", "sent-1")])

    async def test_start_failure_reports_bridge_error(self):
        async def ignore(_message):
            return None

        link = NodeLink(FAKE, ["die"], ignore)
        with self.assertRaises(BridgeError) as caught:
            await link.start(timeout=10)
        self.assertEqual(caught.exception.code, 3000)

    async def test_lost_connection_calls_back_with_code(self):
        lost: asyncio.Future = asyncio.get_running_loop().create_future()

        async def ignore(_message):
            return None

        async def on_lost(error):
            lost.set_result(error)

        link = NodeLink(FAKE, ["serve"], ignore, on_lost)
        await link.start()
        with self.assertRaises(BridgeError):
            await link.call("crash", timeout=5)
        error = await asyncio.wait_for(lost, timeout=5)
        self.assertEqual(error.code, 1006)
        await link.stop()


if __name__ == "__main__":
    unittest.main()
