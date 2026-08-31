#!/usr/bin/env python3
"""Static contracts for crash-safe MCV hook initialization."""

from pathlib import Path
import unittest


SOURCE = Path(__file__).with_name("DawnWarriorSkillCompat.cpp")


class VideoHookContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_video_hook_never_creates_dummy_d3d_devices(self) -> None:
        self.assertNotIn("InstallSharedVideoHooks", self.source)
        self.assertNotIn("dummyDevice", self.source)
        self.assertNotIn("kVideoHookRetryCount", self.source)
        self.assertNotIn("kVideoHookRetryMilliseconds", self.source)

    def test_diagnostics_load_is_followed_by_loadlibrary_rechain(self) -> None:
        install = self.source[self.source.index("DWORD WINAPI InstallHooks") :]
        install = install[: install.index("return 0;")]
        diagnostics_load = install.index('LoadLibraryA("WzFileLogger.dll")')
        rechain = install.index("InstallLoadLibraryHook()", diagnostics_load)
        first_skill_patch = install.index("for (const HookSite& hook : kHooks)")
        self.assertLess(diagnostics_load, rechain)
        self.assertLess(rechain, first_skill_patch)


if __name__ == "__main__":
    unittest.main()
