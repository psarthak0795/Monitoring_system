import unittest

from media_activity import _media_app_matches_foreground_process


class MediaActivityTests(unittest.TestCase):
    def test_supported_browser_media_identity_matches(self):
        self.assertTrue(
            _media_app_matches_foreground_process(
                "chrome.exe", "Chrome.YouTube"
            )
        )

    def test_unrelated_process_does_not_match_media_identity(self):
        self.assertFalse(
            _media_app_matches_foreground_process(
                "notepad.exe", "Chrome.YouTube"
            )
        )

    def test_missing_media_identity_is_not_activity(self):
        self.assertFalse(_media_app_matches_foreground_process("vlc.exe", ""))


if __name__ == "__main__":
    unittest.main()