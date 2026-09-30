import unittest

from activity_detection import _is_long_running_activity


class LongRunningActivityTests(unittest.TestCase):
    def test_video_download_in_browser_is_activity(self):
        self.assertTrue(_is_long_running_activity("chrome.exe", "Downloading report.zip"))

    def test_script_runners_are_activity(self):
        for executable in ("powershell.exe", "python.exe", "node.exe", "cmd.exe", "wscript.exe"):
            with self.subTest(executable=executable):
                self.assertTrue(_is_long_running_activity(executable, ""))

    def test_remote_desktop_clients_are_activity(self):
        for executable in ("mstsc.exe", "msrdc.exe", "AnyDesk.exe", "rustdesk.exe"):
            with self.subTest(executable=executable):
                self.assertTrue(_is_long_running_activity(executable, "Remote session"))

    def test_unrelated_idle_window_is_not_activity(self):
        self.assertFalse(_is_long_running_activity("notepad.exe", "notes.txt"))
        self.assertFalse(_is_long_running_activity("chrome.exe", "Documentation"))


if __name__ == "__main__":
    unittest.main()