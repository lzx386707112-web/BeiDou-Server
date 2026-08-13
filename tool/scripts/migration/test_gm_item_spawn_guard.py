#!/usr/bin/env python3
"""Contract checks for the GM one-click item generator crash guard."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROVIDER = ROOT / "gms-server/src/main/java/org/gms/server/ItemInformationProvider.java"
CONVERSATION = ROOT / "gms-server/src/main/java/org/gms/scripting/npc/NPCConversationManager.java"
SCRIPT = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/一键刷道具.js"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    provider = PROVIDER.read_text(encoding="utf-8")
    conversation = CONVERSATION.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")

    require("public boolean itemDataExists(int itemId)" in provider,
            "missing server-side item-data check")
    require("return getItemData(itemId) != null;" in provider,
            "item-data check does not inspect the actual WZ record")
    require("public boolean canGenerateItem(int itemid)" in conversation,
            "missing NPC-safe item generation API")
    require("public boolean hasItemData(int itemid)" in conversation,
            "missing NPC item-data diagnostic API")
    require("ii.getName(itemid) != null && ii.itemDataExists(itemid)" in conversation,
            "NPC-safe API must require both a string name and actual item data")

    guard = script.index("if (cm.canGenerateItem(selection))")
    gain = script.index("cm.gainItem(selection,1)")
    missing_message = script.index("缺少完整的服务端数据")
    require(guard < gain, "item generation is not protected before gainItem")
    require(missing_message > gain, "missing-data branch has no safe user-facing message")
    require("if (1)" not in script, "unconditional item generation guard remains")

    print("GM item spawn guard contract passed")


if __name__ == "__main__":
    main()
