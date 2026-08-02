#!/usr/bin/env python3
"""Build a client-only compatibility fallback for Arcana mob 8644001."""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BROKEN_MOB_ID = 8644001
VISUAL_MOB_ID = 8644002
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/8644001_兼容版_使用8644002视觉")

sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzImage, WzKey  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_actions(path: Path) -> list[str]:
    image = WzImage.from_bytes(
        path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
    )
    image.parse()
    return [child.name for child in image.root.children()]


def main() -> int:
    broken = ROOT / f"clien/Data/Mob/{BROKEN_MOB_ID}.img"
    visual = ROOT / f"clien/Data/Mob/{VISUAL_MOB_ID}.img"
    output = DESTINATION / f"Client/Data/Mob/{BROKEN_MOB_ID}.img"
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(visual, output)

    if output.read_bytes() != visual.read_bytes():
        raise RuntimeError("written compatibility IMG differs from the visual source")
    actions = parse_actions(output)
    expected_actions = parse_actions(visual)
    if actions != expected_actions:
        raise RuntimeError(f"written action tree changed: {actions}")

    readme = f"""# {BROKEN_MOB_ID} 客户端兼容版

实机结果表明：地图 `450005131` 将 `{BROKEN_MOB_ID}` 替换为
`{VISUAL_MOB_ID}` 后不再黑屏；地图 `450005120` 只刷新
`{BROKEN_MOB_ID}`，怪物显示后立即黑屏。因此本版本保留服务端怪物 ID，
仅将客户端 `Mob/{BROKEN_MOB_ID}.img` 替换为已验证正常的
`Mob/{VISUAL_MOB_ID}.img` 视觉树。

- 服务端经验、掉落、任务和刷怪 ID 不变。
- `{BROKEN_MOB_ID}` 的客户端外观与动作会暂时显示为 `{VISUAL_MOB_ID}`。
- 不需要替换服务端 XML 或地图 XML。
- 兼容 IMG SHA256：`{sha256(output)}`
- 原 `{BROKEN_MOB_ID}` SHA256：`{sha256(broken)}`
- 正常 `{VISUAL_MOB_ID}` SHA256：`{sha256(visual)}`
- 动作树：`{', '.join(actions)}`

测试时只替换 Client 文件并重新打包 `Mob.wz`，然后使用原版地图测试
`450005120` 和 `450005131`。
"""
    readme_path = DESTINATION / "README_测试说明.md"
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(readme, encoding="utf-8")
    print(
        f"mob={BROKEN_MOB_ID} visual={VISUAL_MOB_ID} "
        f"sha256={sha256(output)} actions={actions}"
    )
    print(f"output={DESTINATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
