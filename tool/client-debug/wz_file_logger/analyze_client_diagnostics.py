#!/usr/bin/env python3
"""Summarize one BeiDou client diagnostic session into an actionable report."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIAGNOSTICS_DIR = ROOT / "clien" / "diagnostics"
DEFAULT_CLIENT_ROOT = ROOT / "clien"
LINE_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) "
    r"\[seq=(?P<seq>\d+)\] \[tid=(?P<tid>\d+)\] (?P<payload>.*)$"
)
FIELD_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>\"[^\"]*\"|\S+)")


@dataclass(frozen=True)
class Event:
    time: str
    seq: int
    tid: int
    kind: str
    fields: dict[str, str]
    raw: str


def parse_event(line: str) -> Event | None:
    match = LINE_RE.match(line.lstrip("\ufeff").rstrip("\r\n"))
    if not match:
        return None
    fields = {
        item.group("key"): item.group("value").strip('"')
        for item in FIELD_RE.finditer(match.group("payload"))
    }
    return Event(
        time=match.group("time"),
        seq=int(match.group("seq")),
        tid=int(match.group("tid")),
        kind=fields.get("event", "unknown"),
        fields=fields,
        raw=match.group("payload"),
    )


def read_events(log_path: Path) -> list[Event]:
    return [
        event
        for line in log_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        if (event := parse_event(line)) is not None
    ]


def as_float(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def as_int(value: str | None) -> int:
    try:
        return int(value, 0) if isinstance(value, str) else int(value or 0)
    except (TypeError, ValueError):
        return 0


def classify(events: list[Event]) -> tuple[str, str]:
    if any(event.kind == "crash" for event in events):
        return "客户端异常崩溃", "crash"
    hangs = [event for event in events if event.kind == "hang_detected"]
    if hangs:
        reasons = {event.fields.get("reason") for event in hangs}
        if "window_unresponsive" in reasons:
            return "客户端窗口无响应（黑屏/卡死）", "hang"
        return "客户端持续高 CPU", "high_cpu"
    if any(event.kind == "manual_dump" for event in events):
        return "已手动捕获黑屏/卡死现场", "manual"
    if events and not any(event.kind == "session_end" for event in events):
        return "会话非正常结束（强退、断电或诊断器未捕获的崩溃）", "abrupt"
    return "未检测到崩溃或卡死", "clean"


def suspicious_resources(events: list[Event], limit: int = 8) -> list[tuple[str, int, list[str]]]:
    scores: dict[str, int] = defaultdict(int)
    reasons: dict[str, list[str]] = defaultdict(list)

    def add(path: str | None, score: int, reason: str) -> None:
        if not path or path == "(none)":
            return
        scores[path] += score
        if reason not in reasons[path]:
            reasons[path].append(reason)

    for event_index, event in enumerate(events):
        path = event.fields.get("path")
        status = event.fields.get("status")
        if event.kind == "resource_open" and status == "failed":
            add(path, 100, f"打开失败，Win32 错误 {event.fields.get('error', '?')}")
        elif event.kind == "resource_read" and status == "failed":
            add(path, 120, f"读取失败，Win32 错误 {event.fields.get('error', '?')}")
        elif event.kind == "resource_read":
            elapsed = as_int(event.fields.get("elapsed_ms"))
            add(path, min(60, 10 + elapsed // 10), f"慢读取 {elapsed} ms")
        elif event.kind == "crash":
            add(event.fields.get("last_resource"), 90, "崩溃前最后访问")
        elif event.kind == "health" and event.fields.get("window") == "hung":
            add(event.fields.get("last_resource"), 45, "窗口无响应时仍是最后资源")
        elif event.kind == "hang_detected":
            recent_health = next(
                (item for item in reversed(events[:event_index]) if item.kind == "health"),
                None,
            )
            if recent_health:
                add(recent_health.fields.get("last_resource"), 60, "卡死/高负载前最后访问")

    ranked = sorted(scores, key=lambda path: (-scores[path], path.lower()))
    return [(path, scores[path], reasons[path]) for path in ranked[:limit]]


def resource_read_ranges(events: list[Event]) -> dict[str, tuple[int, int]]:
    ranges: dict[str, tuple[int, int]] = {}
    for event in events:
        if event.kind == "resource_read":
            path = event.fields.get("path")
            offset = as_int(event.fields.get("offset"))
            size = as_int(event.fields.get("read"))
        elif event.kind in {"health", "crash"}:
            path = event.fields.get("last_resource")
            offset = as_int(event.fields.get("resource_offset"))
            size = as_int(event.fields.get("resource_bytes"))
        else:
            continue
        if path and path != "(none)":
            ranges[path] = (offset, max(size, 1))
    return ranges


def local_resource_path(resource_path: str, client_root: Path) -> Path | None:
    normalized = resource_path.replace("/", "\\")
    marker = normalized.lower().find("\\data\\")
    if marker >= 0:
        relative = normalized[marker + 1 :]
    elif normalized.lower().startswith("data\\"):
        relative = normalized
    else:
        return None
    candidate = client_root.joinpath(*relative.split("\\"))
    try:
        candidate.resolve().relative_to(client_root.resolve())
    except ValueError:
        return None
    return candidate


def resolve_img_nodes(resource_path: str, offset: int, size: int, client_root: Path) -> tuple[list[str], str | None]:
    local_path = local_resource_path(resource_path, client_root)
    if local_path is None or local_path.suffix.lower() != ".img" or not local_path.is_file():
        return [], None
    try:
        wz_python = ROOT / "tool" / "wz-python"
        if str(wz_python) not in sys.path:
            sys.path.insert(0, str(wz_python))
        from wzpy import WzImage, WzKey, detect_region_from_img

        with local_path.open("rb") as file:
            header = file.read(4096)
        region = detect_region_from_img(header) or "GMS"
        image = WzImage.from_file(str(local_path), key=WzKey.for_region(region), name=local_path.name)
        root = image.parse()
        read_end = offset + max(size, 1)
        matches: list[tuple[int, int, str, str]] = []

        def visit(node, path: str) -> None:
            ranges = []
            for offset_name, length_name, label in (
                ("_value_offset", "_value_length", "value"),
                ("_payload_offset", "_payload_length", "string"),
                ("_png_offset", "_png_length", "canvas"),
                ("_data_offset", "_data_length", "data"),
            ):
                start = getattr(node, offset_name, None)
                length = getattr(node, length_name, None)
                if isinstance(start, int) and isinstance(length, int) and length > 0:
                    ranges.append((start, start + length, label))
            for start, end, label in ranges:
                if start < read_end and offset < end:
                    overlap = min(end, read_end) - max(start, offset)
                    matches.append((-overlap, end - start, path, label))
            for child in node.children():
                visit(child, f"{path}/{child.name}")

        visit(root, local_path.name)
        matches.sort()
        nodes = [f"{path} ({label})" for _, _, path, label in matches[:5]]
        warnings = getattr(image, "parse_warnings", [])
        warning = "；".join(str(item) for item in warnings[:3]) if warnings else None
        return nodes, warning
    except Exception as exc:
        return [], f"节点反解失败：{exc}"


def build_report(
    log_path: Path,
    events: list[Event],
    *,
    client_root: Path | None = None,
) -> str:
    verdict, verdict_code = classify(events)
    health = [event for event in events if event.kind == "health"]
    crashes = [event for event in events if event.kind == "crash"]
    hangs = [event for event in events if event.kind == "hang_detected"]
    dumps = [event for event in events if event.kind == "dump" and event.fields.get("status") == "ok"]
    failures = [
        event
        for event in events
        if event.kind in {"resource_open", "resource_read"} and event.fields.get("status") == "failed"
    ]
    slow_reads = [
        event
        for event in events
        if event.kind == "resource_read" and as_int(event.fields.get("elapsed_ms")) >= 50
    ]
    ranked = suspicious_resources(events)
    read_ranges = resource_read_ranges(events)

    lines = [
        "# BeiDou 客户端诊断报告",
        "",
        f"- 日志：`{log_path}`",
        f"- 结论：**{verdict}**",
        f"- 有效事件：{len(events)}",
        f"- 资源失败：{len(failures)}；慢读取：{len(slow_reads)}；dump：{len(dumps)}",
    ]

    if health:
        peak_cpu = max(health, key=lambda event: as_float(event.fields.get("cpu_core_pct")))
        peak_memory = max(health, key=lambda event: as_int(event.fields.get("working_set_mb")))
        peak_handles = max(health, key=lambda event: as_int(event.fields.get("handles")))
        lines.extend(
            [
                "",
                "## 性能峰值",
                "",
                f"- 单核 CPU：{peak_cpu.fields.get('cpu_core_pct', '0')}%（{peak_cpu.time}）",
                f"- 工作集：{peak_memory.fields.get('working_set_mb', '0')} MB（{peak_memory.time}）",
                f"- 句柄数：{peak_handles.fields.get('handles', '0')}（{peak_handles.time}）",
            ]
        )

    lines.extend(["", "## 最可疑资源", ""])
    if ranked:
        for path, score, reasons in ranked:
            lines.append(f"- `{path}`（证据分 {score}）：{'；'.join(reasons)}")
    else:
        lines.append("- 没有发现能关联到具体 IMG/WZ 的失败证据。")

    if client_root is not None and ranked:
        lines.extend(["", "## 资源节点反解", ""])
        resolved_any = False
        for path, _, _ in ranked:
            offset, size = read_ranges.get(path, (0, 1))
            nodes, warning = resolve_img_nodes(path, offset, size, client_root)
            if nodes:
                resolved_any = True
                lines.append(f"- `{path}` @ `{offset:#x}`：" + "；".join(f"`{node}`" for node in nodes))
            elif warning:
                lines.append(f"- `{path}` @ `{offset:#x}`：{warning}")
        if not resolved_any:
            lines.append("- 本次文件读取区间没有精确覆盖可解析的 Canvas/Sound/Video/标量数据；请结合 dump 调用栈继续定位。")

    lines.extend(["", "## 关键时间线", ""])
    manual_dumps = [event for event in events if event.kind == "manual_dump"]
    important = failures + hangs + manual_dumps + crashes + dumps
    important.sort(key=lambda event: event.seq)
    if important:
        for event in important[-20:]:
            details = " ".join(
                f"{key}={value}"
                for key, value in event.fields.items()
                if key not in {"event", "session"}
            )
            lines.append(f"- {event.time} `{event.kind}` {details}")
    else:
        lines.append("- 没有崩溃、卡死或资源失败事件。")

    if dumps:
        lines.extend(["", "## Dump 文件", ""])
        lines.extend(f"- `{event.fields.get('path')}`" for event in dumps)

    lines.extend(["", "## 建议", ""])
    if failures:
        lines.append("- 先核对失败资源是否存在、文件名大小写、访问权限，以及客户端与服务端资源版本是否一致。")
    if verdict_code == "crash":
        crash = crashes[-1]
        lines.append(
            f"- 用 WinDbg 打开 dump，优先检查 `{crash.fields.get('module', '(unknown)')}`"
            f" + `{crash.fields.get('module_offset', '?')}` 的调用栈。"
        )
    elif verdict_code in {"hang", "high_cpu", "manual"}:
        lines.append("- 用 WinDbg 打开 hang/high-cpu dump，检查主线程和占用 CPU 线程是否在重复解析同一资源节点。")
    elif verdict_code == "abrupt":
        if any(event.kind == "session_start" for event in events):
            lines.append("- 诊断 DLL 已加载，但进程在异常过滤器运行前被终止；下次黑屏时按住 `Ctrl+F12` 约 2 秒，看到 dump 后再强退。")
        else:
            lines.append("- 当前没有 session_start；确认 `WzFileLogger.dll` 已加载，并检查安全软件是否拦截日志写入。")
    else:
        lines.append("- 本次证据未复现问题；黑屏时按住 `Ctrl+F12` 约 2 秒，并至少保留进程 5 秒。")
    return "\n".join(lines) + "\n"


def newest_log(directory: Path) -> Path:
    logs = list(directory.glob("session-*.log"))
    if not logs:
        raise FileNotFoundError(f"未找到诊断日志：{directory}")
    return max(logs, key=lambda path: path.stat().st_mtime_ns)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", type=Path, help="session-*.log；默认分析最新会话")
    parser.add_argument("--diagnostics-dir", type=Path, default=DEFAULT_DIAGNOSTICS_DIR)
    parser.add_argument("--output", type=Path, help="同时写入 Markdown 报告")
    args = parser.parse_args()

    try:
        log_path = args.log or newest_log(args.diagnostics_dir)
        events = read_events(log_path)
        if not events:
            raise ValueError(f"日志中没有可解析事件：{log_path}")
        report = build_report(log_path, events, client_root=DEFAULT_CLIENT_ROOT)
        if args.output:
            args.output.write_text(report, encoding="utf-8")
        sys.stdout.write(report)
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
