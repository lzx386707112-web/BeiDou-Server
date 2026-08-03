from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import analyze_client_diagnostics as diagnostics


def line(seq: int, payload: str) -> str:
    return f"2026-08-03 12:00:00.{seq:03d} [seq={seq}] [tid=10] {payload}"


class AnalyzeClientDiagnosticsTest(unittest.TestCase):
    def test_crash_report_correlates_last_resource_and_dump(self) -> None:
        log_lines = [
            line(1, "event=session_start session=test pid=1"),
            line(2, 'event=resource_open status=ok handle=1 error=0 path="Data\\Mob\\8900000.img"'),
            line(3, 'event=health cpu_core_pct=99.5 working_set_mb=800 handles=300 window=responsive last_resource="Data\\Mob\\8900000.img"'),
            line(4, 'event=crash code=0xc0000005 module="ResMan.dll" module_offset=0x123 last_resource="Data\\Mob\\8900000.img"'),
            line(5, 'event=dump status=ok reason=crash path="diagnostics\\crash-test.dmp"'),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "session-test.log"
            log_path.write_text("\ufeff" + "\n".join(log_lines), encoding="utf-8")
            events = diagnostics.read_events(log_path)
            report = diagnostics.build_report(log_path, events)

        self.assertIn("客户端异常崩溃", report)
        self.assertIn("Data\\Mob\\8900000.img", report)
        self.assertIn("ResMan.dll", report)
        self.assertIn("99.5%", report)
        self.assertIn("crash-test.dmp", report)

    def test_hang_report_prioritizes_failed_and_last_resource(self) -> None:
        events = [
            diagnostics.parse_event(line(1, "event=session_start session=test")),
            diagnostics.parse_event(line(2, 'event=resource_open status=failed error=2 path="Data\\Map\\broken.img"')),
            diagnostics.parse_event(line(3, 'event=health cpu_core_pct=100.0 working_set_mb=512 handles=100 window=hung last_resource="Data\\Map\\loop.img"')),
            diagnostics.parse_event(line(4, "event=hang_detected reason=window_unresponsive")),
        ]
        valid_events = [event for event in events if event is not None]
        report = diagnostics.build_report(Path("session-test.log"), valid_events)

        self.assertIn("客户端窗口无响应", report)
        self.assertIn("Data\\Map\\broken.img", report)
        self.assertIn("打开失败", report)
        self.assertIn("Data\\Map\\loop.img", report)

    def test_clean_session_is_not_reported_as_abrupt(self) -> None:
        events = [
            diagnostics.parse_event(line(1, "event=session_start session=test")),
            diagnostics.parse_event(line(2, "event=session_end reason=process_detach")),
        ]
        verdict, code = diagnostics.classify([event for event in events if event is not None])
        self.assertEqual("未检测到崩溃或卡死", verdict)
        self.assertEqual("clean", code)

    def test_manual_dump_classifies_black_screen_before_forced_exit(self) -> None:
        events = [
            diagnostics.parse_event(line(1, "event=session_start session=test")),
            diagnostics.parse_event(line(2, "event=manual_dump hotkey=Ctrl+F12")),
            diagnostics.parse_event(line(3, 'event=dump status=ok reason=manual path="diagnostics\\manual-test.dmp"')),
        ]
        valid_events = [event for event in events if event is not None]
        report = diagnostics.build_report(Path("session-test.log"), valid_events)

        self.assertIn("已手动捕获黑屏/卡死现场", report)
        self.assertIn("manual-test.dmp", report)

    def test_abrupt_session_recommends_manual_dump_when_dll_loaded(self) -> None:
        events = [
            diagnostics.parse_event(line(1, "event=session_start session=test")),
            diagnostics.parse_event(line(2, "event=health cpu_core_pct=74.5 window=responsive")),
        ]
        report = diagnostics.build_report(
            Path("session-test.log"),
            [event for event in events if event is not None],
        )

        self.assertIn("诊断 DLL 已加载", report)
        self.assertIn("Ctrl+F12", report)


if __name__ == "__main__":
    unittest.main()
