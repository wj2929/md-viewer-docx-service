import importlib
from app.presets import DOCX_PRESETS, STYLE_ORDER, VALID_STYLES, HeadingStyleDef


class TestValidStyles:
    def test_contains_preview_and_legacy_styles(self):
        assert VALID_STYLES == {"preview", "standard", "official", "internal", "report"}
        assert STYLE_ORDER == ("preview", "standard", "official", "internal", "report")

    def test_presets_keys_match(self):
        assert set(DOCX_PRESETS.keys()) == {"preview", "official", "internal", "report"}


class TestDocxPresets:
    REQUIRED_KEYS = {
        "display_name", "page_margins", "title_font", "title_size",
        "heading_styles", "body_font", "body_size",
    }

    def test_each_preset_has_required_keys(self):
        for name, preset in DOCX_PRESETS.items():
            required_keys = self.REQUIRED_KEYS
            if name == "preview":
                required_keys = self.REQUIRED_KEYS - {"heading_styles"}
            missing = required_keys - set(preset.keys())
            assert not missing, f"Preset '{name}' missing keys: {missing}"

    def test_heading_styles_are_heading_style_def(self):
        for name, preset in DOCX_PRESETS.items():
            if name == "preview":
                continue
            for level, style in preset["heading_styles"].items():
                assert isinstance(style, HeadingStyleDef), (
                    f"Preset '{name}' level {level}: expected HeadingStyleDef, got {type(style)}"
                )

    def test_page_margins_have_all_directions(self):
        for name, preset in DOCX_PRESETS.items():
            margins = preset["page_margins"]
            for key in ("top", "bottom", "left", "right"):
                assert key in margins, f"Preset '{name}' missing margin '{key}'"
                assert isinstance(margins[key], (int, float))


class TestHeadingStyleDef:
    def test_default_bold_is_false(self):
        h = HeadingStyleDef("宋体", 12)
        assert h.bold is False

    def test_explicit_bold(self):
        h = HeadingStyleDef("黑体", 16, bold=True)
        assert h.bold is True
        assert h.font == "黑体"
        assert h.size == 16


class TestZeroDependency:
    def test_presets_module_has_no_docx_imports(self):
        source = importlib.util.find_spec("app.presets")
        with open(source.origin) as f:
            content = f.read()
        assert "from docx" not in content
        assert "import docx" not in content
