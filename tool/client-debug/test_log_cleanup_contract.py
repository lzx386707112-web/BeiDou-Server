#!/usr/bin/env python3
"""Static contracts for per-launch client DLL log cleanup."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class LogCleanupContractTest(unittest.TestCase):
    LOG_OWNERS = {
        "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp": (
            "DawnWarriorSkillCompat.log",
            "CreateThread",
        ),
        "tool/client-debug/damage-skin-compat/BeiDouDamageSkinCompat.cpp": (
            "BeiDouDamageSkinCompat.log",
            "CreateThread",
        ),
        "tool/client-debug/karing-scene-compat/KaringSceneCompat.cpp": (
            "KaringSceneCompat.log",
            "CreateThread",
        ),
        "tool/client-debug/fps-limit/BeiDouFpsLimit.cpp": (
            "BeiDou30FpsLimit.log",
            "CreateThread",
        ),
        "tool/client-video/D3D8Proxy.cpp": (
            "BeiDouVideoProxy.log",
            'LogLine("LOAD:',
        ),
        "tool/client-video/BeiDouVideo.cpp": (
            "BeiDouVideo.log",
            "new (std::nothrow) Player",
        ),
    }

    def test_each_source_owned_log_is_deleted_before_first_writer_starts(self) -> None:
        for relative_path, (log_name, first_writer) in self.LOG_OWNERS.items():
            with self.subTest(source=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                attach = source[source.rindex('extern "C" BOOL WINAPI DllMain') :]
                cleanup = attach.index(f'DeleteFileA("{log_name}")')
                self.assertLess(cleanup, attach.index(first_writer))

    def test_diagnostics_tree_is_removed_before_new_session_directory(self) -> None:
        source = (
            ROOT / "tool/client-debug/wz_file_logger/WzFileLogger.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("FindFirstFileW", source)
        self.assertIn("DeleteFileW", source)
        self.assertIn("RemoveDirectoryW", source)
        init_paths = source[source.index("static void InitPaths") :]
        cleanup = init_paths.index("RemoveDirectoryTree(g_diagnosticsDir)")
        create = init_paths.index("CreateDirectoryW(g_diagnosticsDir")
        self.assertLess(cleanup, create)


if __name__ == "__main__":
    unittest.main()
