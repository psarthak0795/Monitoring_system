import unittest

from system_state import is_locked_desktop, is_locked_process


class SystemStateTests(unittest.TestCase):
    def test_known_locked_desktops_are_detected(self):
        self.assertTrue(is_locked_desktop("Winlogon"))
        self.assertTrue(is_locked_desktop("secure"))

    def test_normal_desktop_is_not_locked(self):
        self.assertFalse(is_locked_desktop("Default"))

    def test_lock_screen_processes_are_detected(self):
        self.assertTrue(is_locked_process("LogonUI.exe"))
        self.assertTrue(is_locked_process("LockApp.exe"))

    def test_normal_process_is_not_locked(self):
        self.assertFalse(is_locked_process("explorer.exe"))


if __name__ == "__main__":
    unittest.main()