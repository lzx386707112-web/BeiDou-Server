from pathlib import Path
import unittest


SOURCE = Path(__file__).with_name("BeiDouSetItemCompat.cpp").read_text(encoding="utf-8")


class SetItemPanelLayoutTest(unittest.TestCase):
    def require(self, fragment: str) -> None:
        self.assertIn(fragment, SOURCE, f"missing panel layout contract: {fragment}")

    def test_reference_panel_dimensions_and_palette(self) -> None:
        self.require("constexpr int kNativePanelWidth = 236;")
        self.require("constexpr int kNativeLineHeight = 16;")
        self.require("NativePanelLineCount(*set) * kNativeLineHeight + 28")
        self.require("CreateNativeFont(gNativeFontTitle, 0xFFFFE137)")
        self.require("CreateNativeFont(gNativeFontActive, 0xFFFFFFFF)")
        self.require("CreateNativeFont(gNativeFontLabel, 0xFFD2D2D2)")
        self.require("CreateNativeFont(gNativeFontDim, 0xFF90949D)")

    def test_reference_panel_text_hierarchy(self) -> None:
        self.require('wsprintfW(line, L"%s (%d/%d)"')
        self.require("CenteredTextX(line)")
        self.require('DrawNativeText(canvas, gNativeFontTitle, kPanelLeft, y, L"套装效果")')
        self.require('wsprintfW(line, L"[%d件]", bonus.required)')
        self.require('wsprintfW(line, L"%s +%d%s", StatLabel(value.key), value.value')
        self.assertNotIn("件套效果", SOURCE)
        self.assertNotIn("已激活", SOURCE)

    def test_equipment_name_and_type_use_separate_columns(self) -> None:
        self.require("DrawNativeText(canvas, font, kPanelLeft, y, wide);")
        self.require("int typeX = RightAlignedTextX(line);")
        self.require("TrimTextToWidth(wide, typeX - kPanelLeft - 6);")
        self.require("DrawNativeText(canvas, font, typeX, y, line);")

    def test_star_panel_is_limited_to_weapons(self) -> None:
        self.require("return itemId >= 1302000 && itemId < 1493000;")
        self.require("if (!IsWeaponItem(itemId)) { HideStarPanel(); return; }")

    def test_star_capacity_level_boundaries(self) -> None:
        expected = (
            "if (requiredLevel <= 94) return 5;",
            "if (requiredLevel <= 107) return 8;",
            "if (requiredLevel <= 117) return 10;",
            "if (requiredLevel <= 127) return 15;",
            "if (requiredLevel <= 137) return 20;",
            "return 25;",
        )
        for fragment in expected:
            self.require(fragment)

    def test_star_panel_reads_the_client_required_level(self) -> None:
        self.require("constexpr uintptr_t kGetEquipItem = 0x005CA785;")
        self.require("constexpr uintptr_t kGetSecureInt = 0x00416563;")
        self.require("constexpr size_t kEquipReqLevelOffset = 0x60;")
        self.require("static_cast<unsigned char*>(equipItem) + kEquipReqLevelOffset")
        self.require("*reinterpret_cast<int*>(requiredLevel + 0x08)")

    def test_star_rows_are_grouped_and_centered(self) -> None:
        self.require("constexpr int kStarAdvance = 9;")
        self.require("constexpr int kStarGroupGap = 4;")
        self.require("return capacity > 15 ? 2 : 1;")
        self.require("return row == 0 ? (capacity > 15 ? 15 : capacity) : capacity - 15;")
        self.require("((count - 1) / 5) * kStarGroupGap")
        self.require("int x = (width - StarRowWidth(count)) / 2;")
        self.require("if (column && column % 5 == 0) x += kStarGroupGap;")

    def test_star_panel_reads_and_caches_current_stars(self) -> None:
        self.require("constexpr size_t kEquipOwnerOffset = 0xE0;")
        self.require("int ReadStarMarker(void* equip, int capacity)")
        self.require("static_cast<unsigned char*>(equip) + kEquipOwnerOffset")
        self.require("marker[0] != 0xA1 || marker[1] != 0xEF")
        self.require("int gPendingCurrentStars = 0;")
        self.require("int gStarPanelCurrentStars = 0;")
        self.require("gStarPanelCurrentStars == currentStars")
        self.require("RenderStarPanel(drawCanvas, nativeWidth, capacity, currentStars);")
        self.assertNotIn("constexpr int kCurrentStars = 0;", SOURCE)
        self.require("firstStar + column < currentStars ? gStarFontLit : gStarFontDim")
        self.require("CreateNativeFont(gStarFontLit, 0xFFFFD83D)")
        self.require("CreateNativeFont(gStarFontDim, 0xFF737B86)")

    def test_internal_star_marker_is_hidden_from_native_tooltip(self) -> None:
        self.require("constexpr uintptr_t kEquipOwnerTextCall = 0x008E8D16;")
        self.require("constexpr uintptr_t kAssignString = 0x00414617;")
        self.require("int ParseStarMarker(const unsigned char* owner, int capacity)")
        self.require("void __fastcall HookEquipOwnerText")
        self.require('>= 0 ? "" : text;')
        self.require("CanPatchCall(kEquipOwnerTextCall, kAssignString)")
        self.require("PatchCall(kEquipOwnerTextCall, reinterpret_cast<void*>(&HookEquipOwnerText))")
        self.require("int markerStars = ReadStarMarker(equip, capacity);")
        self.require("int currentStars = markerStars >= 0 ? markerStars : 0;")
        self.require("unsigned char* owner = markerStars >= 0")
        self.require("unsigned char ownerFirst = owner ? owner[0] : 0;")
        self.require("if (owner) owner[0] = 0;")
        self.require("gRealEquipTooltip(self, equip);")
        self.require("if (owner) owner[0] = ownerFirst;")

if __name__ == "__main__":
    unittest.main()
