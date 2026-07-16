from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import hustlenest


class PackageIdentityTests(unittest.TestCase):
    def test_python_package_uses_hustlenest_identity_only(self) -> None:
        root = Path(__file__).resolve().parent.parent
        legacy_name = "cyber" + "lablog"
        self.assertTrue((root / "hustlenest" / "__init__.py").is_file())
        self.assertFalse((root / legacy_name).exists())
        self.assertIsNotNone(importlib.util.find_spec("hustlenest"))
        self.assertIsNone(importlib.util.find_spec(legacy_name))
        self.assertTrue(hustlenest.__version__.startswith("v"))

    def test_build_spec_targets_hustlenest_package(self) -> None:
        root = Path(__file__).resolve().parent.parent
        legacy_name = "cyber" + "lablog"
        spec = (root / "HustleNest.spec").read_text(encoding="utf-8").casefold()
        self.assertIn(r"hustlenest\\main.py", spec)
        self.assertNotIn(legacy_name, spec)


if __name__ == "__main__":
    unittest.main()
