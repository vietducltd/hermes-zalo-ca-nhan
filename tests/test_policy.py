import unittest

from policy import GroupRule, Settings, chunk_text, contains_phrase, fold, is_resume, mask_id, wants_human


class HandoffKeywordTests(unittest.TestCase):
    def test_detects_keywords_with_and_without_accents(self):
        self.assertTrue(wants_human("Tôi muốn hoàn tiền"))
        self.assertTrue(wants_human("toi muon HOAN TIEN gap"))
        self.assertTrue(wants_human("cho em hoan tiền"))
        self.assertTrue(wants_human("Shop gửi lại mã OTP giúp em"))
        self.assertTrue(wants_human("cho mình gặp người thật"))

    def test_common_words_do_not_trigger(self):
        self.assertFalse(wants_human("Khoá học này học theo lộ trình nào?"))
        self.assertFalse(wants_human("Sản phẩm có gì? Làm thế nào để đăng ký?"))
        self.assertFalse(wants_human("the best course"))
        self.assertFalse(wants_human("mình hỏi về laptop"))

    def test_wrong_accent_is_a_different_word(self):
        self.assertTrue(contains_phrase("đọc số thẻ giúp em", "số thẻ"))
        self.assertTrue(contains_phrase("doc so the giup em", "số thẻ"))
        self.assertFalse(contains_phrase("so thế nào được", "số thẻ"))

    def test_extra_keywords_from_config(self):
        self.assertFalse(wants_human("cho em hỏi về bảo hành"))
        self.assertTrue(wants_human("cho em hỏi về bảo hành", ["bảo hành"]))

    def test_resume_phrase(self):
        self.assertTrue(is_resume("Trợ lý trả lời tiếp"))
        self.assertTrue(is_resume("tro ly tra loi tiep."))
        self.assertFalse(is_resume("trợ lý ơi trả lời tiếp câu trước đi"))

    def test_fold_keeps_length(self):
        self.assertEqual(fold("Đường Thẻ"), "duong the")


class SettingsTests(unittest.TestCase):
    def test_empty_config_blocks_everyone(self):
        settings = Settings.from_extra({})
        self.assertFalse(settings.allows(kind="user", thread_id="u1", sender_id="u1", mentions=[], own_id="bot"))
        self.assertFalse(settings.allows(kind="group", thread_id="g1", sender_id="u1", mentions=["bot"], own_id="bot"))

    def test_dm_allowlist(self):
        settings = Settings.from_extra({"allowed_users": ["u1"]})
        self.assertTrue(settings.allows(kind="user", thread_id="u1", sender_id="u1", mentions=[], own_id="bot"))
        self.assertFalse(settings.allows(kind="user", thread_id="u2", sender_id="u2", mentions=[], own_id="bot"))

    def test_group_needs_allowlist_and_mention(self):
        settings = Settings.from_extra({"allowed_groups": {"g1": {"enabled": True, "require_mention": True}}})
        ask = dict(kind="group", sender_id="u1", own_id="bot")
        self.assertTrue(settings.allows(thread_id="g1", mentions=["bot"], **ask))
        self.assertFalse(settings.allows(thread_id="g1", mentions=[], **ask))
        self.assertFalse(settings.allows(thread_id="g2", mentions=["bot"], **ask))

    def test_group_without_mention_requirement(self):
        settings = Settings.from_extra({"allowed_groups": {"g1": {"enabled": True, "require_mention": False}}})
        self.assertTrue(settings.allows(kind="group", thread_id="g1", sender_id="u1", mentions=[], own_id="bot"))

    def test_disabled_group_and_missing_enabled_flag_stay_closed(self):
        settings = Settings.from_extra({"allowed_groups": {"g1": {"enabled": False}, "g2": {"require_mention": False}}})
        for group in ("g1", "g2"):
            self.assertFalse(settings.allows(kind="group", thread_id=group, sender_id="u1", mentions=["bot"], own_id="bot"))

    def test_numeric_ids_from_yaml_are_matched_as_text(self):
        settings = Settings.from_extra({"allowed_users": [123456789], "allowed_groups": {987654321: {"enabled": True}}})
        self.assertTrue(settings.allows(kind="user", thread_id="123456789", sender_id="123456789", mentions=[], own_id="bot"))
        self.assertTrue(settings.allows(kind="group", thread_id="987654321", sender_id="u1", mentions=["bot"], own_id="bot"))

    def test_group_list_form_uses_default_mention_rule(self):
        self.assertEqual(Settings.from_extra({"allowed_groups": ["g1"]}).groups, {"g1": GroupRule(True, True)})
        relaxed = Settings.from_extra({"allowed_groups": ["g1"], "require_mention": False})
        self.assertEqual(relaxed.groups, {"g1": GroupRule(True, False)})

    def test_pause_seconds_and_replies(self):
        settings = Settings.from_extra({"handoff_seconds": "3600", "handoff_message": " Đã báo quản lý. ", "resume_message": ""})
        self.assertEqual(settings.pause_seconds, 3600)
        self.assertEqual(settings.replies["handoff"], "Đã báo quản lý.")
        self.assertEqual(settings.replies["resume"], Settings().replies["resume"])
        self.assertEqual(Settings.from_extra({"handoff_seconds": "sai"}).pause_seconds, 86400)


class TextTests(unittest.TestCase):
    def test_chunks_respect_limit_and_keep_all_words(self):
        text = "xin chào " * 500
        chunks = chunk_text(text, 120)
        self.assertTrue(all(0 < len(chunk) <= 120 for chunk in chunks))
        self.assertEqual(" ".join(chunks).split(), text.split())

    def test_empty_text_gives_no_chunks(self):
        self.assertEqual(chunk_text("   "), [])

    def test_long_word_is_cut_hard(self):
        self.assertEqual([len(chunk) for chunk in chunk_text("a" * 250, 100)], [100, 100, 50])

    def test_mask_id_hides_real_id(self):
        self.assertNotIn("123456", mask_id("123456"))
        self.assertEqual(mask_id("123456"), mask_id("123456"))


if __name__ == "__main__":
    unittest.main()
