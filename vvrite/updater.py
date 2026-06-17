"""Sparkle 2 based update controller."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import objc
from Foundation import NSBundle, NSLog


REPOSITORY_RELEASES_URL = "https://github.com/shaircast/vvrite/releases"
DEFAULT_APPCAST_URL = (
    "https://github.com/shaircast/vvrite/releases/latest/download/appcast.xml"
)
SPARKLE_FRAMEWORK_NAME = "Sparkle.framework"


def framework_path_from_private_frameworks(private_frameworks_path: str | None) -> str | None:
    """Return the expected Sparkle.framework path for an app bundle Frameworks dir."""
    if not private_frameworks_path:
        return None
    return str(Path(private_frameworks_path) / SPARKLE_FRAMEWORK_NAME)


def repo_vendor_framework_path() -> str:
    """Return the local vendored Sparkle.framework path used by source builds/tests."""
    return str(Path(__file__).resolve().parents[1] / "vendor" / "Sparkle" / SPARKLE_FRAMEWORK_NAME)


def candidate_framework_paths() -> list[str]:
    """Return possible Sparkle.framework locations, ordered by runtime preference."""
    candidates: list[str] = []

    env_path = os.environ.get("SPARKLE_FRAMEWORK_PATH", "").strip()
    if env_path:
        candidates.append(env_path)

    main_bundle = NSBundle.mainBundle()
    embedded_path = framework_path_from_private_frameworks(
        main_bundle.privateFrameworksPath()
    )
    if embedded_path:
        candidates.append(embedded_path)

    seen: set[str] = set()
    unique: list[str] = []
    for path in candidates:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


class SparkleUpdater:
    """Thin PyObjC bridge around Sparkle's SPUStandardUpdaterController."""

    def __init__(
        self,
        controller_class=None,
        framework_paths: Callable[[], list[str]] = candidate_framework_paths,
    ):
        self._controller_class = controller_class
        self._framework_paths = framework_paths
        self._controller = None
        self._load_error: str | None = None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def is_available(self) -> bool:
        return self._controller is not None or self._resolve_controller_class() is not None

    def start(self) -> bool:
        """Start Sparkle's updater using its standard UI."""
        if self._controller is not None:
            return True

        controller_class = self._resolve_controller_class()
        if controller_class is None:
            return False

        try:
            controller = (
                controller_class.alloc()
                .initWithStartingUpdater_updaterDelegate_userDriverDelegate_(
                    True, None, None
                )
            )
        except AttributeError:
            controller = (
                controller_class.alloc()
                .initWithUpdaterDelegate_userDriverDelegate_(None, None)
            )
        except Exception as exc:
            self._load_error = str(exc)
            NSLog(f"Sparkle updater failed to start: {exc}")
            return False

        self._controller = controller
        return True

    def check_for_updates(self, sender=None) -> bool:
        """Run Sparkle's user-initiated update check."""
        if not self.start():
            return False
        self._controller.checkForUpdates_(sender)
        return True

    def automatically_checks_for_updates(self) -> bool | None:
        """Return Sparkle's persisted automatic-check setting when available."""
        updater = self._sparkle_updater()
        if updater is None:
            return None
        return bool(updater.automaticallyChecksForUpdates())

    def set_automatically_checks_for_updates(self, enabled: bool) -> bool:
        """Persist the automatic-check setting through Sparkle."""
        updater = self._sparkle_updater()
        if updater is None:
            return False
        updater.setAutomaticallyChecksForUpdates_(bool(enabled))
        return True

    def _sparkle_updater(self):
        if not self.start():
            return None
        return self._controller.updater()

    def _resolve_controller_class(self):
        if self._controller_class is not None:
            return self._controller_class

        for framework_path in self._framework_paths():
            if not os.path.isdir(framework_path):
                continue
            try:
                objc.loadBundle("Sparkle", globals(), bundle_path=framework_path)
                self._controller_class = objc.lookUpClass("SPUStandardUpdaterController")
                self._load_error = None
                return self._controller_class
            except Exception as exc:
                self._load_error = f"{framework_path}: {exc}"
                NSLog(f"Sparkle framework could not be loaded from {framework_path}: {exc}")

        if self._load_error is None:
            self._load_error = "Sparkle.framework not found"
        return None
