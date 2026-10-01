import tempfile
import unittest
from pathlib import Path

from store import EVERYONE, StateDB


class StateDBTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db = StateDB(Path(self.folder.name) / "sub" / "state.sqlite3")

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def test_each_message_is_processed_once(self):
        self.assertTrue(self.db.first_time("m1"))
        self.assertFalse(self.db.first_time("m1"))
        self.assertTrue(self.db.first_time(""))

    def test_pause_and_resume_one_customer(self):
        self.db.pause("thread", "khach", 60)
        self.assertTrue(self.db.is_paused("thread", "khach"))
        self.assertFalse(self.db.is_paused("thread", "nguoi-khac"))
        self.db.resume("thread", "khach")
        self.assertFalse(self.db.is_paused("thread", "khach"))

    def test_thread_wide_pause_covers_everyone(self):
        self.db.pause("thread", EVERYONE, 60)
        self.assertTrue(self.db.is_paused("thread", "bat-ky-ai"))
        self.db.resume("thread", "bat-ky-ai")
        self.assertFalse(self.db.is_paused("thread", "bat-ky-ai"))

    def test_expired_pause_is_ignored(self):
        self.db.pause("thread", "khach", -1)
        self.assertFalse(self.db.is_paused("thread", "khach"))

    def test_contacts_and_sent_messages(self):
        self.db.remember_contact("g1", "group", "u1", "Khách A")
        self.db.remember_contact("g1", "group", "u1", "Khách A đổi tên")
        self.assertEqual([row[:4] for row in self.db.contacts()], [("g1", "group", "u1", "Khách A đổi tên")])
        self.assertEqual(self.db.kind_of("g1"), "group")
        self.assertIsNone(self.db.kind_of("la"))
        self.db.mark_sent("m9")
        self.assertTrue(self.db.was_sent("m9"))
        self.assertFalse(self.db.was_sent("m0"))


if __name__ == "__main__":
    unittest.main()
