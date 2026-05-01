import importlib
from app.presets import (
    DOCX_PRESETS,
    STYLE_ORDER,
    VALID_STYLES,
    HeadingStyleDef,
    NON_PREVIEW_BLOCK_STYLES,
)


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


class TestNonPreviewBlockStyles:
    def test_cover_legacy_styles_only(self):
        assert set(NON_PREVIEW_BLOCK_STYLES) == {"standard", "official", "internal", "report"}
        assert "preview" not in NON_PREVIEW_BLOCK_STYLES

    def test_official_table_width_fits_a4_content_area(self):
        official = NON_PREVIEW_BLOCK_STYLES["official"]
        assert official.table.content_width_cm <= 15.6
        assert official.image.max_width_cm <= official.table.content_width_cm

    def test_internal_and_report_content_width_matches_table_contract(self):
        for style in ("internal", "report"):
            margins = DOCX_PRESETS[style]["page_margins"]
            content_width = 21.0 - margins["left"] - margins["right"]
            assert NON_PREVIEW_BLOCK_STYLES[style].table.content_width_cm <= content_width

    def test_non_preview_styles_keep_compact_visual_rhythm(self):
        assert DOCX_PRESETS["internal"]["line_spacing_multiple"] <= 1.35
        assert DOCX_PRESETS["report"]["line_spacing_multiple"] <= 1.3
        assert NON_PREVIEW_BLOCK_STYLES["official"].table.body_font_size <= 9.5

    def test_report_does_not_enlarge_tiny_images(self):
        image = NON_PREVIEW_BLOCK_STYLES["report"].image
        assert image.min_width_source_threshold_cm == 8.0


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
