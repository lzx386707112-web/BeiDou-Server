# v83 旧客户端动态伤害皮肤迁移与兼容实现

## 1. 文档目的

本文记录某 v83 旧客户端动态伤害皮肤功能的完整实现、逆向证据、资源转换规则、服务端链路、
NPC 交互、构建部署、验证方法和故障排查。目标是让未参与本次调试的开发者仅依据本文和仓库源码，
就能在同一客户端上复现功能，并能把方案移植到另一个旧客户端版本。

最终实机结果已经确认：玩家可在指定功能 NPC 中浏览 850 个伤害皮肤的预览和名称，
点击后立即切换；选择会保存到角色数据库，重新登录后自动恢复；普通、暴击和 Miss 路径均不会再因
缺少资源节点而冻结或黑屏。

本文适用于以下代码和资源：

- 客户端：目标 v83 旧客户端，32 位 Windows 程序，GMS WZ 编码。
- 源资源：从 TMS 中提取的伤害皮肤资源，并按旧端结构进行兼容修改。
- 服务端：Java 21、Maven、MySQL/Flyway。
- 客户端扩展：32 位 MinGW DLL 注入环境。

本文已经脱敏：`<...>` 表示由实现者按自身工程替换的目录、脚本或模块；示例 DLL 名称、日志前缀、
导出函数名同样是通用占位命名。文中只保留实现所必需的 WZ 内部资源键、协议值和逆向地址，不包含
个人目录、现网 NPC 名称/编号、具体客户端名称或构建指纹。

> 本项目是兼容迁移，不是把 TMS 资源原样复制给旧客户端。旧客户端运行时访问了哪些节点、
> 使用什么 COM 接口和对象生命周期，才是输出结构的最终标准。工具能解析 IMG 不等于客户端能安全使用。

## 2. 最终架构

整个功能分为资源、运行时、通信和持久化四层：

```text
从 TMS 提取并整理的皮肤、像素和名称
                |
                | migrate_damage_skins.py
                v
Effect/DamageSkin.img                 NPC 预览
Effect/DamageSkin/<skinId>.img        运行时四组字形
DamageSkinCatalog.java                服务端 ID/名称白名单
damage-skin-catalog.json              生成清单
                |
                v
NPC setDamageSkin(skinId)
       -> UPDATE characters.damageSkinId
       -> packet [0x017B:uint16 LE][skinId:int32 LE]
       -> 数据包桥接 DLL 解包
       -> DamageSkin_SetSkin(skinId)
       -> 伤害皮肤兼容 DLL 在下一次 Effect_Hit 前替换四组缓存
       -> 原生 CAnimationDisplayer 按旧端逻辑绘制
```

默认皮肤 ID 为 `0`。选择 `0` 时不加载自定义 IMG，而是恢复 DLL 首次捕获并持有的
`BasicEff.img` 原始四组缓存。

## 3. 文件清单

### 3.1 输入资源

皮肤、实际 Canvas 像素和显示名称均从 TMS 资源中提取，再由生成器按旧端契约修改。文档不绑定
任何个人目录；实现时通过生成器配置项传入本机的 TMS 资源目录。

目标旧客户端自己的 `BasicEff.img` 只作为结构、尺寸、origin 及兼容节点基线。它不是 TMS 输入，
也不得被生成器改写。

### 3.2 生成器及测试

第 5.6 节直接给出完整生成器代码，第 11.5 节直接给出完整独立契约测试。为便于后续命令引用，本文
假定两段代码分别保存为 `generate_damage_skins.py` 和 `verify_damage_skins.py`；文件名可自行更改，
实现不依赖仓库目录结构。两者都通过命令行参数接收本机输入和输出路径。

将 IMG 目录打包为 WZ 仍需要实现者已有的 v83/GMS WZ 打包工具，本文用 `<wz-pack-script>` 表示。

### 3.3 生成资源

```text
<client-effect-img-dir>/DamageSkin.img
<client-effect-img-dir>/DamageSkin/<skinId>.img
<generated-doc-dir>/damage-skin-catalog.json
<server-source-dir>/DamageSkinCatalog.java
```

资源用途必须分开：

- `Effect/DamageSkin.img/preview/<skinId>`：NPC 使用的 `160x60` 预览。
- `Effect/DamageSkin/<skinId>.img`：实战时按需加载的四组伤害字形。
- JSON：生成统计、名称、跳过原因及契约信息。
- Java：服务端可选 ID 和名称的唯一白名单。

### 3.4 DLL、服务端和 NPC

```text
<damage-skin-dll-source>        伤害字形缓存替换与导出接口
<damage-skin-dll-build-script>  32 位 DLL 构建脚本
<packet-bridge-source>          自定义包接收和 DamageSkin_SetSkin 桥接
<packet-bridge-build-script>    32 位桥接 DLL 构建脚本
<client-dir>/DamageSkinCompat.dll
<client-dir>/PacketBridgeCompat.dll

<db-migration-script>           characters.damageSkinId 字段迁移
<server-source-dir>/DamageSkinCatalog.java
<server-source-dir>/DamageSkinService.java
<npc-api-source>                NPC 脚本 API 的四个薄封装
<send-opcode-source>            0x17B 发送 opcode
<packet-creator-source>         6 字节选择包构造器
<login-handler-source>          登录恢复调用
<target-npc-script>             预览、分页和点击切换逻辑
<packet-test-source>            数据包字节契约测试
```

## 4. 必须遵守的旧端资源契约

### 4.1 四组固定目录

`CAnimationDisplayer` 不认识现代伤害皮肤的任意结构。它持有并使用四个 `IWzProperty` 缓存：

```text
NoRed0: 0 1 2 3 4 5 6 7 8 9 Miss
NoRed1: 0 1 2 3 4 5 6 7 8 9
NoCri0: 0 1 2 3 4 5 6 7 8 9
NoCri1: 0 1 2 3 4 5 6 7 8 9 effect
```

每个皮肤因此不是 40 张，而是 **42 张运行时 Canvas**：40 张皮肤数字，加上两个从旧客户端基线
逐像素复制的兼容节点。

现代 TMS 某些皮肤使用 `NoCri1/effect3` 或其他新节点，不能据此把旧端的 `effect` 改名或省略。
当前客户端代码硬编码读取 `NoCri1/effect`。同理，Miss 路径从 `NoRed0/Miss` 读取。

### 4.2 画布格式、尺寸和 origin

全部输出 Canvas 必须使用：

```text
WZ region/key = GMS
format         = 1
format2        = 0
pixel format   = ARGB4444
```

现代数字的每一张图先解码成 RGBA，再等比缩放并居中到 `BasicEff.img` 对应
`<group>/<digit>` 的精确宽高。输出 origin 必须逐项复制该旧端数字的 origin。禁止把现代宽高和
origin 原样下放，否则数字排版、层定位乃至旧端内部假设都可能被破坏。

当前投影函数的核心逻辑是：

```python
def fit_to_size(source, size):
    source = source.convert("RGBA")
    scale = min(size[0] / source.width, size[1] / source.height)
    scaled_size = (
        max(1, min(size[0], round(source.width * scale))),
        max(1, min(size[1], round(source.height * scale))),
    )
    resized = source.resize(scaled_size, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", size)
    output.alpha_composite(
        resized,
        ((size[0] - resized.width) // 2,
         (size[1] - resized.height) // 2),
    )
    return output
```

创建 Canvas 时强制写入旧端格式：

```python
canvas.width, canvas.height = pixels.size
canvas.format, canvas.format2 = 1, 0
canvas._png_data = encode_canvas_payload(
    pixels, 1, pixels.width, pixels.height,
    key=GMS_KEY, listwz=False, zlib_level=9,
)
canvas.add(WzVectorProperty("origin", origin[0], origin[1], canvas))
```

### 4.3 动画数字降级

现代元数据中数字节点可能还套有帧目录。本实现只取帧 `0`，因为 v83 的原生伤害显示缓存期待直接的
数字 Canvas，而不是现代动画结构。`linked_canvas()` 会沿 `0` 节点下钻，并解析：

```text
Etc/_Canvas/DamageSkin.img/...
```

形式的 `_outlink`。链接不存在、目标不是 Canvas 或像素为空的皮肤会被跳过并写入清单，不能生成
半套资源。

### 4.4 两个兼容节点必须复制旧端原物

不要尝试从现代皮肤猜测 `Miss` 和暴击 `effect`。安全实现是从 `BasicEff.img` 解码并复制其像素、
尺寸、格式和 origin：

```python
REQUIRED_EXTRAS = {
    "NoRed0": ("Miss",),
    "NoCri1": ("effect",),
}

for group in GROUPS:
    for name in REQUIRED_EXTRAS.get(group, ()):
        pixels, origin = legacy_extras[(group, name)]
        group_dir.add(canvas_property(name, group_dir, pixels, origin=origin))
```

属性顺序也属于契约：数字 `0..9` 在前，额外节点在后。测试必须检查子节点精确顺序，不能只检查名称
集合。

## 5. 生成器实现

### 5.1 读取四类输入

```python
metadata = load_image(SOURCE_META, BMS_KEY)
payload = load_image(SOURCE_CANVAS, BMS_KEY)
strings = load_image(SOURCE_STRINGS, BMS_KEY)
basic = load_image(CLIENT_BASIC, GMS_KEY)
```

所有 IMG 解析后立即拒绝 `truncated` 和任意 `parse_warnings`。TMS 输入使用 BMS key，客户端输出和
基线使用 GMS key，不能混用。

### 5.2 建立旧端模板

先遍历 `BasicEff.img` 的四组、十个数字，记录每项的宽高与 origin；再保存 `Miss` 和 `effect`
像素及 origin。这里的 `BasicEff.img` 只读，生成器不得改写它。

### 5.3 逐皮肤投影

核心循环如下：

```python
for meta_skin in numeric_skins:
    skin_id = int(meta_skin.name)
    projected_groups = {}
    try:
        for group in GROUPS:
            projected_digits = []
            for digit in DIGITS:
                source = linked_canvas(
                    meta_skin.get(f"effect/{group}/{digit}"), payload
                )
                decoded = decode_canvas(source, region="BMS").convert("RGBA")
                projected_digits.append(
                    fit_to_size(decoded, glyph_sizes[(group, digit)])
                )
            projected_groups[group] = projected_digits
    except Exception as error:
        skipped.append({"id": skin_id, "reason": str(error)})
        continue
```

生成每个运行时 IMG 时，四组顺序固定为：

```python
GROUPS = ("NoRed0", "NoRed1", "NoCri0", "NoCri1")
```

名称来自 `Consume.img` 中 `extractID/name`。找不到名称时回退为 `伤害皮肤 <id>`。所有 ID 排序后
同时写入 JSON 与 Java，避免 NPC、服务端白名单和客户端资源各维护一份容易漂移的数据。

### 5.4 为什么拆成 851 个 IMG

早期把全部运行时字形放进一个 `DamageSkin.img`：约 43.5 MB、34,850 张 Canvas。虽然仓库工具能
解析，但旧端会一次性加载并长期持有巨型属性树。最终结构将其拆为：

```text
1 个 DamageSkin.img             只存 850 张 NPC 预览
850 个 DamageSkin/<id>.img     每个只存所选皮肤的 42 张运行时 Canvas
```

这样切换时只加载一个小 IMG，也让资源路径和对象生命周期可控。拆分本身排除了“大型单 IMG 解析”
这一风险，但当时黑屏仍存在；最终根因是缺少旧端额外节点，不能把“拆分后仍黑屏”误解为拆分无效。

### 5.5 生成器写入策略

这些 IMG 都是新建的独立产物，因此允许使用 `encode_image_body()`。它不应用于重写现有
`BasicEff.img` 或其他客户端共享 IMG。所有文件先完整生成并验证到内存，再用同目录临时文件原子替换。

不带 `--apply` 是只读预演，只输出尺寸与哈希；带 `--apply` 才写入：

```bash
python3 generate_damage_skins.py --help
python3 verify_damage_skins.py --help
```

### 5.6 完整生成器代码

下面代码没有省略实现。它要求使用的 WZ Python 库提供 `WzImage`、`WzKey`、属性类型、Canvas
编解码和 `encode_image_body()`；这些 API 名称与本文前述代码一致。将代码保存为
`generate_damage_skins.py`：

```python
#!/usr/bin/env python3
"""Extract TMS damage skins and project them onto a legacy v83 contract."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wzpy-dir", type=Path, required=True)
    parser.add_argument("--tms-meta", type=Path, required=True)
    parser.add_argument("--tms-canvas", type=Path, required=True)
    parser.add_argument("--tms-strings", type=Path, required=True)
    parser.add_argument("--basic-eff", type=Path, required=True)
    parser.add_argument("--effect-output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog-java", type=Path, required=True)
    parser.add_argument("--java-package", required=True)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


ARGS = parse_args()
sys.path.insert(0, str(ARGS.wzpy_dir.resolve()))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzSubProperty
from wzpy.canvas import decode_canvas, encode_canvas_payload
from wzpy.properties import WzIntProperty, WzStringProperty, WzVectorProperty
from wzpy.reader import WzBinaryReader
from wzpy.writer import encode_image_body


BMS_KEY = WzKey.for_region("BMS")
GMS_KEY = WzKey.for_region("GMS")
GROUPS = ("NoRed0", "NoRed1", "NoCri0", "NoCri1")
DIGITS = tuple(str(value) for value in range(10))
REQUIRED_EXTRAS = {"NoRed0": ("Miss",), "NoCri1": ("effect",)}
PREVIEW_SIZE = (160, 60)
PREVIEW_IMG = ARGS.effect_output_dir / "DamageSkin.img"
SKIN_DIR = ARGS.effect_output_dir / "DamageSkin"


def load_image(path: Path, key: WzKey) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=key, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"unsafe IMG parse for {path}: {image.parse_warnings}")
    return image


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def encode_root(root: WzSubProperty, template: WzImage) -> bytes:
    image = WzImage(
        name=root.name,
        parent=None,
        offset=0,
        size=0,
        wz_file=template.wz_file,
    )
    image._root = root
    image._parsed = True
    return encode_image_body(image, gms_reader())


def linked_canvas(node, payload: WzImage) -> WzCanvasProperty:
    current = node
    while isinstance(current, WzSubProperty) and not isinstance(
        current, WzCanvasProperty
    ):
        current = current.child("0")
    if not isinstance(current, WzCanvasProperty):
        raise RuntimeError("digit has no Canvas frame 0")
    outlink = current.child("_outlink")
    if not isinstance(outlink, WzStringProperty):
        raise RuntimeError("digit Canvas has no _outlink")
    prefix = "Etc/_Canvas/DamageSkin.img/"
    value = str(outlink.value).replace("\\", "/")
    if not value.startswith(prefix):
        raise RuntimeError(f"unsupported damage-skin outlink: {value}")
    resolved = payload.root.get(value[len(prefix) :])
    if not isinstance(resolved, WzCanvasProperty) or not resolved.has_pixels():
        raise RuntimeError(f"unresolved damage-skin outlink: {value}")
    return resolved


def fit_to_size(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    source = source.convert("RGBA")
    if source.width <= 0 or source.height <= 0:
        raise RuntimeError("cannot resize an empty Canvas")
    scale = min(size[0] / source.width, size[1] / source.height)
    scaled_size = (
        max(1, min(size[0], round(source.width * scale))),
        max(1, min(size[1], round(source.height * scale))),
    )
    resized = source.resize(scaled_size, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", size)
    output.alpha_composite(
        resized,
        ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2),
    )
    return output


def resolve_sample(
    meta_skin: WzSubProperty,
    payload: WzImage,
    digit_images: list[Image.Image],
) -> Image.Image:
    sample = meta_skin.child("sample")
    if sample is not None:
        try:
            return decode_canvas(linked_canvas(sample, payload), region="BMS").convert(
                "RGBA"
            )
        except RuntimeError:
            pass
    width = sum(image.width for image in digit_images)
    height = max(image.height for image in digit_images)
    composed = Image.new("RGBA", (width, height))
    x = 0
    for image in digit_images:
        composed.alpha_composite(image, (x, height - image.height))
        x += image.width
    return composed


def canvas_property(
    name: str,
    parent: WzSubProperty,
    pixels: Image.Image,
    origin: tuple[int, int] | None = None,
) -> WzCanvasProperty:
    canvas = WzCanvasProperty(name, parent)
    canvas.width, canvas.height = pixels.size
    canvas.format, canvas.format2 = 1, 0
    canvas._png_data = encode_canvas_payload(
        pixels,
        1,
        pixels.width,
        pixels.height,
        key=GMS_KEY,
        listwz=False,
        zlib_level=9,
    )
    canvas._png_length = len(canvas._png_data)
    if origin is not None:
        canvas.add(WzVectorProperty("origin", origin[0], origin[1], canvas))
    return canvas


def item_name(meta_skin: WzSubProperty, strings: WzImage, skin_id: int) -> str:
    extract_id = meta_skin.child("extractID")
    if isinstance(extract_id, WzIntProperty):
        name = strings.root.get(f"{int(extract_id.value)}/name")
        if isinstance(name, WzStringProperty) and str(name.value).strip():
            return str(name.value).strip()
    return f"Damage Skin {skin_id}"


def java_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def build_catalog_java(catalog: list[dict]) -> bytes:
    ids = ", ".join(str(entry["id"]) for entry in catalog)
    names = ",\n".join(
        f'        "{java_string(entry["name"])}"' for entry in catalog
    )
    source = f'''package {ARGS.java_package};

/** Generated from the converted damage-skin catalog. */
public final class DamageSkinCatalog {{
    private static final int[] IDS = {{{ids}}};
    private static final String[] NAMES = {{
{names}
    }};

    private DamageSkinCatalog() {{}}

    public static int[] ids() {{
        return IDS.clone();
    }}

    public static boolean contains(int skinId) {{
        return indexOf(skinId) >= 0;
    }}

    public static String nameOf(int skinId) {{
        int index = indexOf(skinId);
        return index >= 0 ? NAMES[index] : "Unknown Damage Skin";
    }}

    private static int indexOf(int skinId) {{
        int low = 0;
        int high = IDS.length - 1;
        while (low <= high) {{
            int middle = (low + high) >>> 1;
            int candidate = IDS[middle];
            if (candidate < skinId) {{
                low = middle + 1;
            }} else if (candidate > skinId) {{
                high = middle - 1;
            }} else {{
                return middle;
            }}
        }}
        return -1;
    }}
}}
'''
    return source.encode("utf-8")


def legacy_contract(basic: WzImage):
    sizes = {}
    origins = {}
    extras = {}
    for group in GROUPS:
        for digit in DIGITS:
            canvas = basic.root.get(f"{group}/{digit}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"legacy glyph missing: {group}/{digit}")
            origin = canvas.child("origin")
            if not isinstance(origin, WzVectorProperty):
                raise RuntimeError(f"legacy glyph origin missing: {group}/{digit}")
            sizes[(group, digit)] = (int(canvas.width), int(canvas.height))
            origins[(group, digit)] = (int(origin.x), int(origin.y))
        for name in REQUIRED_EXTRAS.get(group, ()):
            canvas = basic.root.get(f"{group}/{name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"legacy damage node missing: {group}/{name}")
            origin = canvas.child("origin")
            if not isinstance(origin, WzVectorProperty):
                raise RuntimeError(f"legacy damage node origin missing: {group}/{name}")
            extras[(group, name)] = (
                decode_canvas(canvas, region="GMS").convert("RGBA"),
                (int(origin.x), int(origin.y)),
            )
    return sizes, origins, extras


def build_outputs() -> tuple[dict[Path, bytes], dict]:
    metadata = load_image(ARGS.tms_meta, BMS_KEY)
    payload = load_image(ARGS.tms_canvas, BMS_KEY)
    strings = load_image(ARGS.tms_strings, BMS_KEY)
    basic = load_image(ARGS.basic_eff, GMS_KEY)
    glyph_sizes, glyph_origins, legacy_extras = legacy_contract(basic)

    preview_root = WzSubProperty("DamageSkin.img")
    preview_dir = WzSubProperty("preview", preview_root)
    preview_root.add(preview_dir)
    catalog = []
    skipped = []
    skin_outputs = {}

    numeric_skins = sorted(
        (node for node in metadata.root.children() if node.name.isdigit()),
        key=lambda node: int(node.name),
    )
    for meta_skin in numeric_skins:
        skin_id = int(meta_skin.name)
        red_zero_images = []
        projected_groups = {}
        try:
            for group in GROUPS:
                projected_digits = []
                for digit in DIGITS:
                    source = linked_canvas(
                        meta_skin.get(f"effect/{group}/{digit}"), payload
                    )
                    decoded = decode_canvas(source, region="BMS").convert("RGBA")
                    projected_digits.append(
                        fit_to_size(decoded, glyph_sizes[(group, digit)])
                    )
                    if group == "NoRed0":
                        red_zero_images.append(decoded)
                projected_groups[group] = projected_digits
            preview = fit_to_size(
                resolve_sample(meta_skin, payload, red_zero_images), PREVIEW_SIZE
            )
        except Exception as error:
            skipped.append({"id": skin_id, "reason": str(error)})
            continue

        preview_dir.add(canvas_property(str(skin_id), preview_dir, preview))
        skin = WzSubProperty(f"{skin_id}.img")
        for group in GROUPS:
            group_dir = WzSubProperty(group, skin)
            skin.add(group_dir)
            for digit, pixels in zip(DIGITS, projected_groups[group]):
                group_dir.add(
                    canvas_property(
                        digit,
                        group_dir,
                        pixels,
                        origin=glyph_origins[(group, digit)],
                    )
                )
            for name in REQUIRED_EXTRAS.get(group, ()):
                pixels, origin = legacy_extras[(group, name)]
                group_dir.add(canvas_property(name, group_dir, pixels, origin))

        path = SKIN_DIR / f"{skin_id}.img"
        skin_outputs[path] = encode_root(skin, metadata)
        catalog.append({"id": skin_id, "name": item_name(meta_skin, strings, skin_id)})

    if not catalog or catalog[0]["id"] != 0:
        raise RuntimeError("default skin ID 0 must be present")

    manifest = {
        "sources": {
            "metadata": ARGS.tms_meta.name,
            "canvas": ARGS.tms_canvas.name,
            "strings": ARGS.tms_strings.name,
            "legacyBaseline": ARGS.basic_eff.name,
        },
        "catalogCount": len(catalog),
        "skippedCount": len(skipped),
        "glyphsPerSkin": 40,
        "runtimeCanvasesPerSkin": 42,
        "previewSize": list(PREVIEW_SIZE),
        "projection": "frame 0, centered into legacy dimensions and origins",
        "resourceLayout": "Effect/DamageSkin/<id>.img/<group>/<node>",
        "catalog": catalog,
        "skipped": skipped,
    }
    outputs = {
        PREVIEW_IMG: encode_root(preview_root, metadata),
        ARGS.manifest: (
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8"),
        ARGS.catalog_java: build_catalog_java(catalog),
    }
    outputs.update(skin_outputs)
    return outputs, manifest


def verify_outputs(outputs: dict[Path, bytes], manifest: dict) -> None:
    basic = load_image(ARGS.basic_eff, GMS_KEY)
    preview = WzImage.from_bytes(
        outputs[PREVIEW_IMG], key=GMS_KEY, name=PREVIEW_IMG.name
    )
    preview.parse()
    if preview.truncated or preview.parse_warnings:
        raise RuntimeError(f"generated preview parse failed: {preview.parse_warnings}")

    extra_pixels = {}
    for group, names in REQUIRED_EXTRAS.items():
        for name in names:
            canvas = basic.root.get(f"{group}/{name}")
            extra_pixels[(group, name)] = decode_canvas(
                canvas, region="GMS"
            ).convert("RGBA").tobytes()

    ids = [entry["id"] for entry in manifest["catalog"]]
    if ids != sorted(set(ids)):
        raise RuntimeError("catalog IDs must be unique and sorted")

    for skin_id in ids:
        preview_canvas = preview.root.get(f"preview/{skin_id}")
        if not isinstance(preview_canvas, WzCanvasProperty):
            raise RuntimeError(f"missing preview: {skin_id}")
        if (int(preview_canvas.format), int(preview_canvas.format2)) != (1, 0):
            raise RuntimeError(f"invalid preview format: {skin_id}")
        if decode_canvas(preview_canvas, region="GMS").getbbox() is None:
            raise RuntimeError(f"transparent preview: {skin_id}")

        path = SKIN_DIR / f"{skin_id}.img"
        skin = WzImage.from_bytes(outputs[path], key=GMS_KEY, name=path.name)
        skin.parse()
        if skin.truncated or skin.parse_warnings:
            raise RuntimeError(f"unsafe generated skin {skin_id}")

        for group in GROUPS:
            group_node = skin.root.get(group)
            expected = DIGITS + REQUIRED_EXTRAS.get(group, ())
            if not isinstance(group_node, WzSubProperty):
                raise RuntimeError(f"missing group: {skin_id}/{group}")
            if tuple(child.name for child in group_node.children()) != expected:
                raise RuntimeError(f"invalid child order: {skin_id}/{group}")

            for digit in DIGITS:
                glyph = skin.root.get(f"{group}/{digit}")
                legacy = basic.root.get(f"{group}/{digit}")
                if not isinstance(glyph, WzCanvasProperty) or not isinstance(
                    legacy, WzCanvasProperty
                ):
                    raise RuntimeError(f"missing glyph: {skin_id}/{group}/{digit}")
                origin = glyph.child("origin")
                legacy_origin = legacy.child("origin")
                actual = (
                    int(glyph.width), int(glyph.height),
                    int(glyph.format), int(glyph.format2),
                    int(origin.x), int(origin.y),
                )
                wanted = (
                    int(legacy.width), int(legacy.height), 1, 0,
                    int(legacy_origin.x), int(legacy_origin.y),
                )
                if actual != wanted:
                    raise RuntimeError(f"glyph contract mismatch: {skin_id}/{group}/{digit}")
                if decode_canvas(glyph, region="GMS").getbbox() is None:
                    raise RuntimeError(f"transparent glyph: {skin_id}/{group}/{digit}")

            for name in REQUIRED_EXTRAS.get(group, ()):
                canvas = skin.root.get(f"{group}/{name}")
                legacy = basic.root.get(f"{group}/{name}")
                origin = canvas.child("origin")
                legacy_origin = legacy.child("origin")
                actual = (
                    int(canvas.width), int(canvas.height),
                    int(canvas.format), int(canvas.format2),
                    int(origin.x), int(origin.y),
                )
                wanted = (
                    int(legacy.width), int(legacy.height),
                    int(legacy.format), int(legacy.format2),
                    int(legacy_origin.x), int(legacy_origin.y),
                )
                if actual != wanted:
                    raise RuntimeError(f"extra-node mismatch: {skin_id}/{group}/{name}")
                pixels = decode_canvas(canvas, region="GMS").convert("RGBA").tobytes()
                if pixels != extra_pixels[(group, name)]:
                    raise RuntimeError(f"extra-node pixels differ: {skin_id}/{group}/{name}")


def reject_stale_skin_files(outputs: dict[Path, bytes]) -> None:
    if not SKIN_DIR.exists():
        return
    expected = {path.resolve() for path in outputs if path.parent == SKIN_DIR}
    stale = sorted(
        path for path in SKIN_DIR.glob("*.img")
        if path.stem.isdigit() and path.resolve() not in expected
    )
    if stale:
        names = ", ".join(path.name for path in stale[:10])
        raise RuntimeError(
            f"stale numeric skin files exist ({names}); use a clean output directory"
        )


def print_hashes(outputs: dict[Path, bytes], manifest: dict) -> None:
    aggregate = hashlib.sha256()
    skin_count = 0
    skin_bytes = 0
    for path in sorted(outputs, key=lambda item: str(item)):
        data = outputs[path]
        if path.parent == SKIN_DIR:
            aggregate.update(path.name.encode("ascii"))
            aggregate.update(hashlib.sha256(data).digest())
            skin_count += 1
            skin_bytes += len(data)
        else:
            print(f"{path.name}: {len(data)} bytes sha256={hashlib.sha256(data).hexdigest()}")
    print(
        f"skins: {skin_count} files, {skin_bytes} bytes, "
        f"aggregate-sha256={aggregate.hexdigest()}"
    )
    print(f"catalog={manifest['catalogCount']} skipped={manifest['skippedCount']}")


def main() -> int:
    outputs, manifest = build_outputs()
    verify_outputs(outputs, manifest)
    reject_stale_skin_files(outputs)
    print_hashes(outputs, manifest)
    if ARGS.apply:
        for path, data in outputs.items():
            atomic_write(path, data)
        print("verified outputs written")
    else:
        print("dry-run complete; pass --apply to write outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

生成器故意不删除旧文件。如果目标目录已有不属于新 catalog 的数字 IMG，它会要求换用干净输出目录，
避免一个文档示例执行后静默删除用户资源。

## 6. 客户端运行时 DLL

### 6.1 当前 EXE 的版本边界

以下地址只对本次验证的目标 EXE 构建有效：

```text
image base                     0x00400000
WZ resource manager pointer    0x00BF14E8
CAnimationDisplayer pointer    0x00BEBF6C
Effect_Hit entry               0x00437D0F
Effect_Hit continuation        0x00437D14
original EAX immediate         0x00A79ACF
```

四组 `IWzProperty*` 缓存在 `CAnimationDisplayer` 对象内：

```text
+0x170  NoRed0
+0x174  NoRed1
+0x188  NoCri0
+0x18C  NoCri1
```

在另一个 EXE 上，必须重新反汇编并确认地址、原始字节、对象布局、调用线程和 COM 接口；不能只改
SHA-256 检查或强行跳过 hook 字节校验。

### 6.2 为什么挂在 Effect_Hit 入口

`DamageSkin_SetSkin()` 可能在网络包处理线程/阶段被调用。它只通过 `InterlockedExchange` 记录请求 ID，
不在包处理现场加载 WZ 或改显示对象。实际替换发生在下一次本地伤害显示进入 `Effect_Hit` 时，此时
原生显示对象已经初始化，且正处于安全的视觉路径。

导出接口保持极小：

```cpp
extern "C" __declspec(dllexport) void DamageSkin_SetSkin(int skinId) {
    if (skinId < 0) skinId = 0;
    InterlockedExchange(&gRequestedSkin, skinId);
    gFailedSkin = -1;
}
```

hook 保存标志与通用寄存器，执行待处理切换，然后还原被覆盖的原始指令并回到 `0x00437D14`：

```cpp
pushfd
pushad
call _ApplyRequestedDamageSkin
popad
popfd
mov eax, 0x00A79ACF
push 0x00437D14
ret
```

安装前 DLL 比较 `0x00437D0F` 处原始 5 字节。若不匹配则拒绝安装，避免在未知版本上写入跳转。

### 6.3 WZ 加载与接口转换

运行时资源路径必须是：

```text
Effect/DamageSkin/<skinId>.img
```

资源管理器 `GetObject` 返回的是 VARIANT 中的 COM 对象。它不能作为任意裸对象直接塞进缓存，必须
通过下列 IID 查询 `IWzProperty`：

```text
986515D9-0A0B-4929-8B4F-718682177B92
```

关键流程：

```cpp
void* image = QueryWzProperty(DetachVariantObject(result));
void* noRed0 = GetChild(image, L"NoRed0");
void* noRed1 = GetChild(image, L"NoRed1");
void* noCri0 = GetChild(image, L"NoCri0");
void* noCri1 = GetChild(image, L"NoCri1");
ComRelease(image);
```

`GetChild()` 的结果也要再次 `QueryInterface(IWzProperty)`。初版把资源结果当作原始对象缓存，表面上
可以取到数据，但对象类型和所有权不符合原生构造器的行为，属于不安全实现。

### 6.4 COM 引用计数

第一次进入 `Effect_Hit` 后，DLL 从四个缓存槽读取默认组并对每项 `AddRef()`，保证以后能恢复默认
皮肤。替换时，新组已各持有一个引用；把指针移入槽后释放旧槽的引用：

```cpp
void ReplaceCacheGroups(void* displayer, void** replacements) {
    for (int i = 0; i < 4; ++i) {
        void** slot = CacheSlot(displayer, kCacheOffsets[i]);
        void* previous = *slot;
        *slot = replacements[i];
        replacements[i] = nullptr; // ownership moved to cache
        ComRelease(previous);
    }
}
```

恢复默认时先对保存的默认组各 `AddRef()`，再走同一替换逻辑。不要把加载 IMG 的父属性提前释放后
继续使用没有独立引用的 child，也不要在换入缓存后再次释放 replacement。

### 6.5 请求去重和失败抑制

DLL 维护：

```text
gRequestedSkin  服务端最后请求的 ID
gAppliedSkin    当前已应用的 ID
gFailedSkin     本轮加载失败的 ID
```

已应用或已失败的同一请求不会在每次攻击中重复加载。收到新的 `DamageSkin_SetSkin()` 后清空失败状态。
如果加载四组中的任意一组失败，则释放本次已获取的全部引用，并保留当前皮肤。

## 7. 服务端到 DLL 的通信

### 7.1 数据包契约

新增发送 opcode：

```java
DAMAGE_SKIN_UPDATE(0x17B)
```

包体只有一个 32 位有符号整数：

```java
public static Packet damageSkinUpdate(int skinId) {
    OutPacket p = OutPacket.create(SendOpcode.DAMAGE_SKIN_UPDATE);
    p.writeInt(skinId);
    return p;
}
```

线上字节契约固定为小端序、总长 6 字节：

```text
offset  size  meaning
0       2     uint16 opcode = 0x017B
2       4     int32 skinId
```

`DamageSkinPacketTest` 必须断言 opcode、ID、总长度和无剩余字节，避免以后无意改变桥接协议。

### 7.2 复用已有数据包桥接 DLL

现有数据包桥接 DLL 已在 `0x004965F1` 接管服务端包分发，因而在同一个 hook 中增加 `0x017B`
分支，动态加载伤害皮肤兼容 DLL 并解析其 `DamageSkin_SetSkin` 导出。部署时由项目自行定义 DLL 文件名：

```cpp
HMODULE module = LoadLibraryA("DamageSkinCompat.dll");
FARPROC selector = GetProcAddress(module, "DamageSkin_SetSkin");
MemoryCopy(&gSetDamageSkin, &selector, sizeof(gSetDamageSkin));
```

接收逻辑严格要求从当前 packet offset 到结尾正好 6 字节：

```cpp
if (opcode == 0x017B) {
    if (packet->offset + 6 == packet->length && gSetDamageSkin != nullptr) {
        int skinId = 0;
        MemoryCopy(&skinId, packet->data + packet->offset + 2, sizeof(skinId));
        gSetDamageSkin(skinId);
    }
    return;
}
```

这意味着部署时两个 DLL 都必须存在，且注入器必须加载数据包桥接 DLL。伤害皮肤 DLL 会由它
`LoadLibraryA`；若项目以后替换桥接模块，也必须保留等价的包接收入口。

## 8. 数据库、服务和登录恢复

### 8.1 数据库迁移

Flyway 脚本为角色表新增字段：

```sql
ALTER TABLE `characters`
    ADD COLUMN `damageSkinId` INT NOT NULL DEFAULT 0;
```

默认 `0` 对应原生皮肤。上线前先确认生产库还没有同名列，并按项目现有 Flyway 流程执行，不能在
脚本已经应用后改写该版本文件。

### 8.2 服务端白名单与持久化

`DamageSkinService` 是 NPC 和登录链路的唯一入口：

- `getSkinIds()`：返回生成目录中所有合法 ID 的副本。
- `getSkinName(id)`：返回相同索引的名称。
- `getSkinId(characterId)`：从数据库读取，并再次用 catalog 校验；非法值回退到 `0`。
- `setSkin(player, id)`：先校验白名单，再更新数据库；只有恰好更新一行才发送切换包。
- `sync(player)`：登录/进频道时读取数据库并向本人发送切换包。

核心事务顺序是“校验 -> 落库 -> 发包”：

```java
if (player == null || !DamageSkinCatalog.contains(skinId)) return false;
statement.setInt(1, skinId);
statement.setInt(2, player.getId());
if (statement.executeUpdate() != 1) return false;
player.sendPacket(PacketCreator.damageSkinUpdate(skinId));
return true;
```

登录处理器在角色加入频道世界前调用：

```java
DamageSkinService.sync(player);
cserv.addPlayer(player);
wserv.addPlayer(player);
```

该设置只发给玩家本人。协议没有角色 ID，也没有必要广播；广播会错误改变其他客户端的本地皮肤。

## 9. NPC 预览与切换

`NPCConversationManager` 暴露四个薄封装：

```java
int[] getDamageSkinIds()
String getDamageSkinName(int skinId)
int getDamageSkinId()
boolean setDamageSkin(int skinId)
```

目标功能 NPC 每页显示 4 个皮肤，预览使用旧端 NPC 图片标记：

```javascript
text += "#L" + i + "##fEffect/DamageSkin.img/preview/" + skinId + "#\r\n";
text += "#b" + cm.getDamageSkinName(skinId) + "#k" + selected + "#l\r\n";
```

选择索引必须限制在当前页的 `[startIndex, endIndex)`，不能直接相信客户端传入的 selection。服务端
还会在 `setSkin()` 再校验 catalog，这是第二道边界。

点击条目后立即更新并退出对话：

```javascript
var skinId = damageSkinIds[selection];
if (!cm.setDamageSkin(skinId)) {
    cm.sendOk("伤害皮肤更换失败，请稍后重试。");
    cm.dispose();
    return;
}
cm.sendOk("已更换为：#b" + cm.getDamageSkinName(skinId) + "#k。\r\n\r\n"
    + "#fEffect/DamageSkin.img/preview/" + skinId + "#");
cm.dispose();
```

切换包只是登记请求。为了遵循正确的客户端视觉阶段，DLL 在玩家下一次产生伤害飘字时真正替换缓存。

## 10. 从零复现

所有命令均在工程根目录执行。尖括号参数按自身目录替换，不要把尖括号原样传给 shell。

### 10.1 前置条件

```text
Python 3 + Pillow
兼容目标 WZ 格式的 IMG 读写库
JDK 21
Maven
i686-w64-mingw32-g++
兼容 v83/GMS 的 WZ 打包工具
从 TMS 中提取的伤害皮肤资源
与地址常量匹配的目标 EXE
```

先确认工作树，保留已有修改：

```bash
git status --short
mvn -version
```

`mvn -version` 显示的 Java version 必须为 21。只安装 JDK 21 但 Maven 仍绑定 JDK 17 时，编译会
报 `无效的目标发行版：21`；应按本机安装位置设置标准 `JAVA_HOME` 后重新确认版本，再运行测试。

### 10.2 生成并验证资源

先做语法检查和只读预演：

```bash
python3 -m py_compile generate_damage_skins.py verify_damage_skins.py

python3 generate_damage_skins.py \
  --wzpy-dir <wz-library-dir> \
  --tms-meta <tms-damage-skin-meta-img> \
  --tms-canvas <tms-damage-skin-canvas-img> \
  --tms-strings <tms-consume-string-img> \
  --basic-eff <legacy-basic-eff-img> \
  --effect-output-dir <client-effect-img-dir> \
  --manifest <manifest-json> \
  --catalog-java <server-catalog-java> \
  --java-package <server-java-package>
```

确认输出数量、跳过原因和哈希合理后写入，再运行契约测试：

```bash
python3 generate_damage_skins.py \
  --wzpy-dir <wz-library-dir> \
  --tms-meta <tms-damage-skin-meta-img> \
  --tms-canvas <tms-damage-skin-canvas-img> \
  --tms-strings <tms-consume-string-img> \
  --basic-eff <legacy-basic-eff-img> \
  --effect-output-dir <client-effect-img-dir> \
  --manifest <manifest-json> \
  --catalog-java <server-catalog-java> \
  --java-package <server-java-package> \
  --apply

python3 verify_damage_skins.py \
  --wzpy-dir <wz-library-dir> \
  --basic-eff <legacy-basic-eff-img> \
  --effect-output-dir <client-effect-img-dir> \
  --manifest <manifest-json> \
  --catalog-java <server-catalog-java> \
  --expected-skins 850
```

生成器再运行一次，并比较第一次后的文件 SHA-256。第二次不得继续改变任何输出。这是生成幂等性要求。

### 10.3 构建 DLL

```bash
<damage-skin-dll-build-script>
<packet-bridge-build-script>
```

构建目标必须是 32 位 PE DLL。脚本使用 `-nostdlib`、固定入口和
`--no-insert-timestamp`，从而减少运行库依赖并使相同源码构建可复现。

### 10.4 构建与测试服务端

只运行本功能的数据包测试：

```bash
mvn -pl <server-module> -Dtest=DamageSkinPacketTest test
```

完整构建：

```bash
mvn -pl <server-module> -am clean package
```

项目编译目标是 Java 21。构建失败时先区分本次链路失败和工作树里其他功能的既有失败，不要为了让
整套测试变绿而放宽伤害皮肤契约。`无效的目标发行版：21` 表示 Maven 使用了低版本 JDK，不是
测试断言失败。

### 10.5 打包实际 Effect.wz

旧客户端运行时从 `Effect.wz` 读取，单独放置 IMG 或 `DamageSkin.dat` 不会满足原生资源路径。
使用版本 83、GMS 编码打包整个客户端 Effect IMG 目录：

```bash
<wz-pack-script> \
  --input <client-effect-img-dir> \
  --output <verification-output-dir>/Effect.wz \
  --version 83 \
  --region gms
```

输出必须指向独立、可写的验证目录，并确保不会覆盖当前运行客户端的文件。先在该目录完成重开和
解码验证，再由部署流程替换客户端文件。

### 10.6 部署文件

客户端运行时至少需要：

```text
Effect.wz
DamageSkinCompat.dll
PacketBridgeCompat.dll
```

服务端需要包含对应 Java、NPC 脚本和数据库迁移的最新构建产物。复制交付前逐文件计算源、目标
SHA-256 并要求一致。不要附带探针、旧 DLL、`DamageSkin.dat`、临时 WZ 或调试基线。

## 11. 强制验证门槛

### 11.1 资源契约测试必须证明什么

`test_damage_skin_contract.py` 应至少验证：

1. catalog 恰有 850 个已排序且不重复的 ID，首项为 `0`。
2. NPC、opcode、DLL 路径和导出接口仍存在。
3. 旧的 `DamageSkin.dat` 和纹理探针路径已移除。
4. 预览 IMG 不包含运行时字形树。
5. 每个皮肤的四组顺序、数字顺序和额外节点顺序精确一致。
6. 每张数字 Canvas 都存在、可解码、非全透明，格式为 ARGB4444。
7. 每张数字的宽高和 origin 与 `BasicEff.img` 对应数字一致。
8. `Miss`、`effect` 的格式、宽高、origin 和解码后像素与 `BasicEff.img` 完全一致。
9. 所有 IMG 均无 truncation 和 parse warnings。
10. Java catalog、JSON catalog 和实际 IMG 文件集合一致。

本次成功版本输出：

```text
damage-skin contract passed: 850 skins, 35700 WZ runtime Canvases, 5 skipped
```

`35,700 = 850 x 42`。如果测试仍报告 `34,000` 或只验证 40 张数字，说明旧端额外节点契约未覆盖。

### 11.2 打包后独立验证

不能只验证源 IMG。必须把实际客户端目录打成 v83/GMS `Effect.wz`，再由独立 reader 重开 WZ：

```text
packed_wz_version=83 region=GMS
packed_skin_count=850
decoded_runtime_canvases=35700
warnings=0 truncated=0
```

验证时至少逐个解析 850 个运行时 IMG，并解码全部 35,700 张 Canvas；还要检查预览数量以及
`BasicEff.img` 保持原始哈希。

### 11.3 发布哈希记录

每次发布都应单独记录目标 EXE、`BasicEff.img`、预览 IMG、所有皮肤 IMG 聚合值、两个 DLL 和最终
`Effect.wz` 的 SHA-256。源数据、工具或任何合法资源变化后，哈希可以改变；应依靠上述契约重新验证，
而不是套用另一套构建的哈希。

校验当前文件可使用：

```bash
sha256sum \
  <client-effect-img-dir>/BasicEff.img \
  <client-effect-img-dir>/DamageSkin.img \
  <client-effect-img-dir>/DamageSkin/3.img \
  <client-dir>/DamageSkinCompat.dll \
  <client-dir>/PacketBridgeCompat.dll
```

### 11.4 实机测试矩阵

离线工具不能证明 Windows/Winlator 运行时稳定。至少完成：

| 场景 | 预期结果 |
| --- | --- |
| 启动、登录、进入频道 | 无“不正确的游戏数据”，登录选择自动同步 |
| NPC 翻页 | 预览和名称匹配，无越界或脚本错误 |
| 选择新皮肤 | 成功提示；下一次攻击显示新样式 |
| 普通非暴击 | `NoRed0/NoRed1` 数字正常 |
| 暴击 | `NoCri0/NoCri1` 数字及附加 effect 正常，不冻结 |
| Miss | 原生 Miss 正常，不访问空节点 |
| 选择 ID 0 | 恢复 `BasicEff` 默认样式 |
| 连续快速切换 | 最终采用最后一次选择，不泄漏或崩溃 |
| 重复攻击 10 分钟以上 | 无逐步卡顿、黑屏或资源耗尽 |
| 换图、换频道、重登 | 选择保持，缓存仍能安全切换 |
| 其他玩家攻击 | 不因本地包广播而改变对方或自己的选择 |

### 11.5 完整独立契约测试代码

下面的测试不导入生成器，也不读取生成器内存对象；它只检查已经写到磁盘的交付候选。将代码保存为
`verify_damage_skins.py`：

```python
#!/usr/bin/env python3
"""Independently verify generated legacy damage-skin resources."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wzpy-dir", type=Path, required=True)
    parser.add_argument("--basic-eff", type=Path, required=True)
    parser.add_argument("--effect-output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog-java", type=Path, required=True)
    parser.add_argument("--expected-skins", type=int)
    parser.add_argument(
        "--require-text",
        action="append",
        default=[],
        metavar="PATH::TEXT",
        help="require a cross-layer source marker; may be repeated",
    )
    parser.add_argument(
        "--forbid-text",
        action="append",
        default=[],
        metavar="PATH::TEXT",
        help="reject an obsolete source marker; may be repeated",
    )
    parser.add_argument(
        "--forbid-path",
        action="append",
        default=[],
        type=Path,
        help="reject an obsolete runtime file; may be repeated",
    )
    return parser.parse_args()


ARGS = parse_args()
sys.path.insert(0, str(ARGS.wzpy_dir.resolve()))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzSubProperty
from wzpy.canvas import decode_canvas
from wzpy.properties import WzVectorProperty


GMS_KEY = WzKey.for_region("GMS")
GROUPS = ("NoRed0", "NoRed1", "NoCri0", "NoCri1")
DIGITS = tuple(str(value) for value in range(10))
REQUIRED_EXTRAS = {"NoRed0": ("Miss",), "NoCri1": ("effect",)}
PREVIEW_SIZE = (160, 60)


def load_image(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError(f"unsafe IMG parse for {path}: {image.parse_warnings}")
    return image


def split_marker(value: str) -> tuple[Path, str]:
    if "::" not in value:
        raise AssertionError(f"source marker must use PATH::TEXT: {value}")
    path, text = value.split("::", 1)
    if not path or not text:
        raise AssertionError(f"source marker must use PATH::TEXT: {value}")
    return Path(path), text


def verify_source_markers() -> None:
    for value in ARGS.require_text:
        path, text = split_marker(value)
        content = path.read_text(encoding="utf-8")
        if text not in content:
            raise AssertionError(f"{path} is missing required marker {text!r}")
    for value in ARGS.forbid_text:
        path, text = split_marker(value)
        content = path.read_text(encoding="utf-8")
        if text in content:
            raise AssertionError(f"{path} still contains obsolete marker {text!r}")
    for path in ARGS.forbid_path:
        if path.exists():
            raise AssertionError(f"obsolete runtime path still exists: {path}")


def parse_java_ids(source: str) -> list[int]:
    match = re.search(
        r"private\s+static\s+final\s+int\[\]\s+IDS\s*=\s*\{(.*?)\};",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError("generated Java catalog has no IDS initializer")
    return [int(value) for value in re.findall(r"\d+", match.group(1))]


def canvas_origin(canvas: WzCanvasProperty, label: str) -> tuple[int, int]:
    origin = canvas.child("origin")
    if not isinstance(origin, WzVectorProperty):
        raise AssertionError(f"missing origin: {label}")
    return int(origin.x), int(origin.y)


def canvas_metadata(canvas: WzCanvasProperty, label: str):
    origin = canvas_origin(canvas, label)
    return (
        int(canvas.width),
        int(canvas.height),
        int(canvas.format),
        int(canvas.format2),
        origin[0],
        origin[1],
    )


def visible_pixels(canvas: WzCanvasProperty, label: str):
    pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
    if pixels.getbbox() is None:
        raise AssertionError(f"transparent Canvas: {label}")
    return pixels


def main() -> int:
    verify_source_markers()

    manifest = json.loads(ARGS.manifest.read_text(encoding="utf-8"))
    catalog = manifest.get("catalog")
    if not isinstance(catalog, list) or not catalog:
        raise AssertionError("manifest catalog is empty")
    ids = [entry["id"] for entry in catalog]
    if ids != sorted(set(ids)) or ids[0] != 0:
        raise AssertionError("catalog IDs must be sorted, unique, and start with 0")
    if ARGS.expected_skins is not None and len(ids) != ARGS.expected_skins:
        raise AssertionError(
            f"expected {ARGS.expected_skins} skins, found {len(ids)}"
        )
    if manifest.get("catalogCount") != len(ids):
        raise AssertionError("manifest catalogCount does not match catalog")
    if manifest.get("glyphsPerSkin") != 40:
        raise AssertionError("manifest glyphsPerSkin must be 40")
    if manifest.get("runtimeCanvasesPerSkin") != 42:
        raise AssertionError("manifest runtimeCanvasesPerSkin must be 42")
    if manifest.get("previewSize") != [160, 60]:
        raise AssertionError("manifest previewSize must be [160, 60]")
    if any(
        not isinstance(entry.get("name"), str)
        or not entry["name"].strip()
        or re.search(r"[#\r\n]", entry["name"])
        for entry in catalog
    ):
        raise AssertionError("catalog contains an empty or unsafe display name")

    java_source = ARGS.catalog_java.read_text(encoding="utf-8")
    if parse_java_ids(java_source) != ids:
        raise AssertionError("Java catalog IDs differ from manifest")
    java_name_count = len(
        re.findall(r'^\s*"(?:[^"\\]|\\.)*"\s*,?\s*$', java_source, re.MULTILINE)
    )
    if java_name_count != len(ids):
        raise AssertionError(
            f"Java catalog name count mismatch: {java_name_count} != {len(ids)}"
        )

    basic = load_image(ARGS.basic_eff)
    preview_path = ARGS.effect_output_dir / "DamageSkin.img"
    skin_dir = ARGS.effect_output_dir / "DamageSkin"
    preview = load_image(preview_path)
    if preview.root.get("skin") is not None:
        raise AssertionError("preview IMG must not contain a runtime skin tree")
    preview_dir = preview.root.get("preview")
    if not isinstance(preview_dir, WzSubProperty):
        raise AssertionError("preview IMG has no preview directory")
    if tuple(child.name for child in preview_dir.children()) != tuple(map(str, ids)):
        raise AssertionError("preview child order differs from catalog")

    actual_skin_files = {
        int(path.stem): path
        for path in skin_dir.glob("*.img")
        if path.stem.isdigit()
    }
    if set(actual_skin_files) != set(ids):
        missing = sorted(set(ids) - set(actual_skin_files))[:10]
        extra = sorted(set(actual_skin_files) - set(ids))[:10]
        raise AssertionError(f"runtime IMG set mismatch; missing={missing}, extra={extra}")

    legacy_extra_pixels = {}
    for group, names in REQUIRED_EXTRAS.items():
        for name in names:
            label = f"BasicEff/{group}/{name}"
            canvas = basic.root.get(f"{group}/{name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise AssertionError(f"missing legacy node: {label}")
            legacy_extra_pixels[(group, name)] = visible_pixels(
                canvas, label
            ).tobytes()

    runtime_canvas_count = 0
    for skin_id in ids:
        preview_canvas = preview.root.get(f"preview/{skin_id}")
        if not isinstance(preview_canvas, WzCanvasProperty):
            raise AssertionError(f"missing preview Canvas: {skin_id}")
        if (
            int(preview_canvas.width),
            int(preview_canvas.height),
            int(preview_canvas.format),
            int(preview_canvas.format2),
        ) != (PREVIEW_SIZE[0], PREVIEW_SIZE[1], 1, 0):
            raise AssertionError(f"preview contract mismatch: {skin_id}")
        visible_pixels(preview_canvas, f"preview/{skin_id}")

        skin = load_image(actual_skin_files[skin_id])
        if tuple(child.name for child in skin.root.children()) != GROUPS:
            raise AssertionError(f"group order mismatch: {skin_id}")

        for group in GROUPS:
            group_node = skin.root.get(group)
            expected_names = DIGITS + REQUIRED_EXTRAS.get(group, ())
            if not isinstance(group_node, WzSubProperty):
                raise AssertionError(f"missing group: {skin_id}/{group}")
            if tuple(child.name for child in group_node.children()) != expected_names:
                raise AssertionError(f"child order mismatch: {skin_id}/{group}")

            for digit in DIGITS:
                label = f"{skin_id}/{group}/{digit}"
                glyph = skin.root.get(f"{group}/{digit}")
                legacy = basic.root.get(f"{group}/{digit}")
                if not isinstance(glyph, WzCanvasProperty):
                    raise AssertionError(f"missing glyph: {label}")
                if not isinstance(legacy, WzCanvasProperty):
                    raise AssertionError(f"missing legacy glyph: {group}/{digit}")
                legacy_meta = canvas_metadata(legacy, f"BasicEff/{group}/{digit}")
                expected_meta = (
                    legacy_meta[0],
                    legacy_meta[1],
                    1,
                    0,
                    legacy_meta[4],
                    legacy_meta[5],
                )
                if canvas_metadata(glyph, label) != expected_meta:
                    raise AssertionError(f"glyph metadata mismatch: {label}")
                visible_pixels(glyph, label)
                runtime_canvas_count += 1

            for name in REQUIRED_EXTRAS.get(group, ()):
                label = f"{skin_id}/{group}/{name}"
                canvas = skin.root.get(f"{group}/{name}")
                legacy = basic.root.get(f"{group}/{name}")
                if not isinstance(canvas, WzCanvasProperty):
                    raise AssertionError(f"missing compatibility node: {label}")
                if not isinstance(legacy, WzCanvasProperty):
                    raise AssertionError(f"missing legacy compatibility node: {group}/{name}")
                if canvas_metadata(canvas, label) != canvas_metadata(
                    legacy, f"BasicEff/{group}/{name}"
                ):
                    raise AssertionError(f"compatibility metadata mismatch: {label}")
                if visible_pixels(canvas, label).tobytes() != legacy_extra_pixels[(group, name)]:
                    raise AssertionError(f"compatibility pixels mismatch: {label}")
                runtime_canvas_count += 1

    expected_canvases = len(ids) * 42
    if runtime_canvas_count != expected_canvases:
        raise AssertionError(
            f"runtime Canvas count mismatch: {runtime_canvas_count} != {expected_canvases}"
        )

    skipped = manifest.get("skipped", [])
    if manifest.get("skippedCount") != len(skipped):
        raise AssertionError("manifest skippedCount does not match skipped list")
    print(
        f"damage-skin contract passed: {len(ids)} skins, "
        f"{runtime_canvas_count} runtime Canvases, {len(skipped)} skipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

跨层源码检查通过重复传参接入，不在测试里写死任何工程路径。例如：

```bash
python3 verify_damage_skins.py \
  --wzpy-dir <wz-library-dir> \
  --basic-eff <legacy-basic-eff-img> \
  --effect-output-dir <client-effect-img-dir> \
  --manifest <manifest-json> \
  --catalog-java <server-catalog-java> \
  --expected-skins 850 \
  --require-text '<npc-script>::#fEffect/DamageSkin.img/preview/' \
  --require-text '<npc-script>::setDamageSkin(skinId)' \
  --require-text '<send-opcode-source>::DAMAGE_SKIN_UPDATE(0x17B)' \
  --require-text '<packet-bridge-source>::0x017B' \
  --require-text '<damage-skin-dll-source>::Effect/DamageSkin/%d.img' \
  --require-text '<damage-skin-dll-source>::DamageSkin_SetSkin' \
  --forbid-text '<damage-skin-dll-source>::DamageSkin.dat' \
  --forbid-path '<client-dir>/DamageSkin.dat'
```

如果实际 DLL 导出函数仍使用其他名称，最后一项 `--require-text` 应填写实际名称；本文的
`DamageSkin_SetSkin` 只是脱敏后的通用示例。

## 12. 逆向证据

以下证据解释了为什么最终方案是替换四组原生缓存，而不是自己创建伤害数字图层：

```text
CAnimationDisplayer constructor   0x00435444
Effect_Hit                        0x00437D0F
other number/Miss path            0x00438A21
monster wrapper                   0x006691D3
normal Effect_Hit return          0x004389E5
CAnimationDisplayer destructor    around 0x00435B6F
```

怪物包装路径在 `0x00669241` 调用 `0x00438A21`，在 `0x0066925B/0x00669263` 调用
`0x00437D0F`。`Effect_Hit` 入口原始代码为：

```asm
00437D0F  mov eax, 00A79ACF
00437D14  call 00A60B98
```

`0x00A60B98` 是旧端 SEH prologue helper。进入函数后，代码立即把选择的四个缓存组复制到局部
COM 智能指针，再根据数字取 Canvas 并创建层。暴击分支在 `0x438163` 之后还会从 `NoCri1` 读取
额外节点；基线中该节点名为 `effect`。另一数字路径则读取 `NoRed0/Miss`。

辅助函数的逆向定位：

```text
0x00403935  property get_item wrapper
0x00403A93  ResMan GetObject wrapper
0x004052AD  QueryInterface-to-IWzProperty helper
0x004032B2  VARIANT-to-IUnknown helper
```

析构器通过 COM `Release` 释放这四组缓存，证明槽中保存的必须是有独立引用的接口指针，而不是借用
指针或任意资源对象。

## 13. 调试历史与根因

### 13.1 `DamageSkin.dat` 外部纹理方案

早期尝试把纹理放入独立 `DamageSkin.dat`，再由 DLL 转换。这个方案绕开了客户端原生 WZ 路径，
而最终部署又必须把 Effect 资源打进 `Effect.wz`；BAT/打包流程也不会自动识别该外部文件。最终完全
移除该路径，统一使用 `Effect/DamageSkin/<id>.img`。

### 13.2 纹理探针采集错对象

`DamageSkinTextureProbe.bin` 曾捕获大量地图素材，却没有伤害数字。这说明探针挂点/对象分类错误，
不能把采集数量当成找到正确纹理的证据。最终根据反汇编直接定位原生伤害显示与缓存，不再依赖全局
纹理采集猜测。

### 13.3 巨型单 IMG

单一运行时 IMG 约 43.5 MB、34,850 张 Canvas，存在旧端一次性解析和持有风险。拆分为按 ID 的小
IMG 后，加载粒度合理，但实机仍会在显示新数字后冻结。这证明单 IMG 是风险点，却不是当时黑屏的
最终根因。

### 13.4 缓存对象类型错误

早期将资源结果作为原始对象缓存，没有复现构造器的 `QueryInterface(IWzProperty)` 行为。后来依据
原生函数修正对象类型和 `AddRef/Release` 生命周期。日志能显示加载成功和新数字出现，证明主数字
链路已经打通，但暴击后仍黑屏，说明还存在更晚的节点访问。

### 13.5 最终根因：资源契约只检查了 40 张数字

成功显示新数字的 v5 日志类似：

```text
LOAD: DamageSkinCompat <version> split-IWzProperty-cache
OK: Effect_Hit native WZ cache hook installed
SELECT: pending WZ damage glyph skin=3
OK: captured BasicEff normal/critical damage glyph groups
OK: applied WZ damage glyph groups skin=3
```

这组日志证明：DLL 注入、包接收、WZ 加载、接口转换、缓存替换和数字 Canvas 都已成功。画面是在数字
显示后冻结，随后黑屏，因此失败发生于同一原生函数的后续访问。反汇编确认暴击路径继续读取
`NoCri1/effect`；生成资源只有 40 张数字，返回了空/失败 COM 路径。Miss 路径还需要
`NoRed0/Miss`。

最终修复不是再换 hook，而是将每个皮肤的运行时契约从 40 扩展到 42，两个额外节点从
`BasicEff.img` 精确复制。用户随后确认实机成功。

这段历史给出一个通用判断规则：

```text
新样式完全不出现      -> 先查包、DLL、资源路径、四组缓存和格式
新样式出现后立即出错  -> 沿原生显示函数继续查后续必需节点，不要推翻已被日志证明的前半链路
```

## 14. 日志判读

数据包桥接日志中应看到：

```text
LOAD: PacketBridgeCompat <version> damage-skin-packet
OK: damage-skin selector loaded
OK: decoded 0x17B skin=<id>
```

伤害皮肤兼容日志中应看到：

```text
LOAD: DamageSkinCompat <version> split-IWzProperty-cache
OK: Effect_Hit native WZ cache hook installed
SELECT: pending WZ damage glyph skin=<id>
OK: captured BasicEff normal/critical damage glyph groups
OK: applied WZ damage glyph groups skin=<id>
```

常见异常：

| 日志/表现 | 含义 | 检查点 |
| --- | --- | --- |
| `selector not present` | 伤害皮肤 DLL 不存在或导出失败 | 文件名、工作目录、`DamageSkin_SetSkin` 导出 |
| `invalid 0x17B` | 服务端和 DLL 包长度不一致 | opcode、小端序、总长 6 字节 |
| `unexpected image base` | EXE 装载基址不匹配 | 客户端版本、ASLR、注入目标 |
| `Effect_Hit bytes do not match` | 目标 EXE 不是已验证版本 | 重新反汇编，不要强制安装 |
| `resource manager is not initialized` | 应用发生得太早或地址错误 | hook 阶段、全局地址 |
| `IMG load failed` | Effect.wz 未包含路径或编码错误 | 打包输入、v83/GMS、文件名 |
| `IWzProperty QueryInterface failed` | 对象或 IID 不匹配 | GetObject 返回值、IID、客户端版本 |
| `group load failed` | 四组目录缺失/拼写错误 | IMG 根节点与属性顺序 |
| 已显示数字后冻结 | 后续兼容节点缺失 | `NoCri1/effect`、`NoRed0/Miss` |
| 皮肤切换后仍是旧样式 | 请求未到或下一击未应用 | 两份日志、opcode、Effect_Hit hook |

## 15. 移植到另一个客户端版本

资源投影原则通常可复用，但 DLL 地址绝对不能照搬。移植步骤为：

1. 固定新 EXE 的 SHA-256、image base 和 WZ 版本/区域。
2. 从怪物伤害包装器定位普通、暴击、Miss 的全部显示入口。
3. 找到 `CAnimationDisplayer` 构造和析构，确认四组缓存偏移及 COM 释放方式。
4. 记录原始缓存从哪个 `BasicEff` 路径加载、是否仍为 `IWzProperty`。
5. 沿普通、暴击和 Miss 的每一条分支列出全部 `get_item` 名称，不能只记录数字 `0..9`。
6. 用目标客户端自己的 `BasicEff.img` 建立尺寸、origin、额外节点和顺序模板。
7. 确认资源管理器全局地址、GetObject 调用约定、IWzProperty IID 和 VARIANT 所有权。
8. 选择只在本地显示安全阶段执行的 hook；网络阶段只登记请求。
9. 安装前校验完整指令边界和原始字节，正确重放覆盖指令。
10. 更新 packet hook 地址和原始字节检查，重新构建 32 位 DLL。
11. 扩展契约测试，覆盖新版本发现的所有额外节点。
12. 完成打包后独立重开、全量解码和完整实机矩阵。

如果新客户端已经原生支持伤害皮肤，应优先使用其原生角色字段和协议，而不是继续替换缓存。

## 16. 完成标准

只有同时满足以下条件，才能视为实现完成：

- 源皮肤、名称和实际 Canvas 链均可解析，跳过项有明确原因。
- 输出结构以目标客户端 `BasicEff.img` 和反汇编访问路径为准。
- 每个皮肤包含 40 个兼容投影数字以及 `Miss`、`effect` 两个基线节点。
- 所有 Canvas 为 GMS ARGB4444，宽高、origin、顺序和可见像素验证通过。
- 850 个运行时 IMG、预览 IMG、JSON 和 Java catalog 一致。
- 生成器第二次运行哈希稳定。
- DLL 只在匹配的 EXE 上安装，COM 接口与引用计数正确。
- `0x17B` 包严格为 6 字节，NPC 输入和服务端 ID 都经过白名单验证。
- 角色选择落库，登录时只同步给本人。
- 实际 `Effect.wz` 以 v83/GMS 打包，重开后全量解析、解码无警告。
- DLL、服务端测试与 `git diff --check` 通过。
- Windows/Winlator 已验证普通、暴击、Miss、恢复默认、重登和长时间重复攻击。

最后执行：

```bash
git diff --check
git status --short
```

检查最终变更集只包含预期源码、生成资源、服务端链路和交付文件。不要把失败探针、旧版 DLL、临时
WZ、日志或基线副本混入部署。
