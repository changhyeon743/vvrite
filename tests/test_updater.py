"""Tests for Sparkle updater integration."""

import unittest

from vvrite import updater


class FakeSPUUpdater:
    def __init__(self):
        self.auto_checks = True

    def automaticallyChecksForUpdates(self):
        return self.auto_checks

    def setAutomaticallyChecksForUpdates_(self, enabled):
        self.auto_checks = bool(enabled)


class FakeController:
    allocated = None

    @classmethod
    def alloc(cls):
        cls.allocated = cls()
        return cls.allocated

    def __init__(self):
        self.started = None
        self.checked_sender = None
        self.fake_updater = FakeSPUUpdater()

    def initWithStartingUpdater_updaterDelegate_userDriverDelegate_(
        self, starting_updater, updater_delegate, user_driver_delegate
    ):
        self.started = bool(starting_updater)
        self.updater_delegate = updater_delegate
        self.user_driver_delegate = user_driver_delegate
        return self

    def checkForUpdates_(self, sender):
        self.checked_sender = sender

    def updater(self):
        return self.fake_updater


class TestSparklePaths(unittest.TestCase):
    def test_framework_path_from_private_frameworks(self):
        self.assertEqual(
            updater.framework_path_from_private_frameworks("/App/Contents/Frameworks"),
            "/App/Contents/Frameworks/Sparkle.framework",
        )

    def test_framework_path_from_missing_private_frameworks(self):
        self.assertIsNone(updater.framework_path_from_private_frameworks(None))
        self.assertIsNone(updater.framework_path_from_private_frameworks(""))

    def test_repo_vendor_framework_path(self):
        self.assertTrue(
            updater.repo_vendor_framework_path().endswith(
                "vendor/Sparkle/Sparkle.framework"
            )
        )


class TestSparkleUpdater(unittest.TestCase):
    def test_start_instantiates_standard_controller(self):
        sparkle = updater.SparkleUpdater(controller_class=FakeController)

        self.assertTrue(sparkle.start())
        self.assertTrue(FakeController.allocated.started)

    def test_check_for_updates_delegates_to_sparkle(self):
        sparkle = updater.SparkleUpdater(controller_class=FakeController)
        sender = object()

        self.assertTrue(sparkle.check_for_updates(sender))
        self.assertIs(FakeController.allocated.checked_sender, sender)

    def test_automatic_check_setting_delegates_to_sparkle(self):
        sparkle = updater.SparkleUpdater(controller_class=FakeController)

        self.assertTrue(sparkle.automatically_checks_for_updates())
        self.assertTrue(sparkle.set_automatically_checks_for_updates(False))
        self.assertFalse(sparkle.automatically_checks_for_updates())

    def test_unavailable_without_framework(self):
        sparkle = updater.SparkleUpdater(framework_paths=lambda: [])

        self.assertFalse(sparkle.start())
        self.assertFalse(sparkle.check_for_updates())
        self.assertIsNone(sparkle.automatically_checks_for_updates())
        self.assertFalse(sparkle.set_automatically_checks_for_updates(True))
        self.assertEqual(sparkle.load_error, "Sparkle.framework not found")


if __name__ == "__main__":
    unittest.main()
