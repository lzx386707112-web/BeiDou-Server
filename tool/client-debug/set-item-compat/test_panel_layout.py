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

if __name__ == "__main__":
    unittest.main()
