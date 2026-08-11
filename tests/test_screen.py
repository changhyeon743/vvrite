"""Window selection for the screen-context capture.

The failure this guards against is silent: picking the wrong window still produces
plausible-looking terms, so nothing looks broken — the corrector just gets spelling
hints from an app the user was not reading.
"""
import os
import unittest
from unittest.mock import MagicMock, patch


def _window(pid, width=1200, layer=0, number=1, owner="App"):
    return {
        "kCGWindowLayer": layer,
        "kCGWindowOwnerPID": pid,
        "kCGWindowOwnerName": owner,
        "kCGWindowNumber": number,
        "kCGWindowBounds": {"X": 0, "Y": 0, "Width": width, "Height": 800},
    }


class TestFocusedWindow(unittest.TestCase):
    def _run(self, windows, focused_pid):
        import vvrite.screen as screen

        quartz = MagicMock()
        quartz.CGWindowListCopyWindowInfo.return_value = windows
        appkit = MagicMock()
        front = MagicMock()
        front.processIdentifier.return_value = focused_pid
        appkit.NSWorkspace.sharedWorkspace.return_value.frontmostApplication.return_value = front
        with patch.dict("sys.modules", {"Quartz": quartz, "AppKit": appkit}):
            return screen._focused_window()

    def test_picks_the_focused_apps_window_not_the_topmost(self):
        """A window can sit above the focused app — a floating panel, a window that
        never took focus. Reading it would describe a screen the user is not using."""
        got = self._run([_window(999, owner="Other"), _window(42, owner="Focused")], 42)
        self.assertEqual(got["kCGWindowOwnerName"], "Focused")

    def test_narrow_focused_window_reads_nothing_rather_than_another_app(self):
        """The old z-order walk skipped narrow windows and fell through to whatever
        was behind, which is worse than no terms at all."""
        self.assertIsNone(self._run([_window(42, width=200), _window(999)], 42))

    def test_menu_bar_and_overlay_layers_are_not_windows(self):
        self.assertIsNone(self._run([_window(42, layer=25)], 42))

    def test_never_captures_vvrite_itself(self):
        """The recording overlay appears at the same moment as this capture."""
        self.assertIsNone(self._run([_window(os.getpid())], os.getpid()))


if __name__ == "__main__":
    unittest.main()
