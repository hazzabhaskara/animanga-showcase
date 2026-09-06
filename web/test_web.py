"""
Unit and Integration Tests for Animanga Showcase Web Deliverables (Milestone 2).

Tests cover:
  - web/generator.py execution and output files
  - data.js payload contract, item counts, and field integrity
  - index.html DOM structure, relative paths, and file:// protocol safety
  - styles.css offline self-containment, design tokens, and dark/light themes
  - app.js file:// compatibility, zero-CORS compliance, and search logic
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
INDEX_HTML = ROOT_DIR / "index.html"
STYLES_CSS = ROOT_DIR / "styles.css"
APP_JS = ROOT_DIR / "app.js"
DATA_JS = ROOT_DIR / "data.js"


class TestWebShowcase(unittest.TestCase):
    """Behavioral and contract tests for the web showcase."""

    def test_all_web_deliverables_exist_and_non_empty(self):
        """Verify all 4 core web deliverables exist in root and have non-zero size."""
        for file_path in [INDEX_HTML, STYLES_CSS, APP_JS, DATA_JS]:
            self.assertTrue(file_path.exists(), f"File missing: {file_path.name}")
            self.assertGreater(
                file_path.stat().st_size,
                0,
                f"File {file_path.name} must not be empty",
            )

    def test_data_js_contract_and_counts(self):
        """Verify data.js declares window.CATALOG_DATA with exactly 219 anime & 47 manga."""
        content = DATA_JS.read_text(encoding="utf-8")
        self.assertIn("window.CATALOG_DATA", content)

        match = re.search(r"window\.CATALOG_DATA\s*=\s*(\{.*?\});?\s*$", content, re.DOTALL)
        self.assertIsNotNone(match, "Could not extract JSON object from window.CATALOG_DATA in data.js")

        data = json.loads(match.group(1))

        # Metadata checks
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["total_anime"], 219)
        self.assertEqual(data["metadata"]["total_manga"], 47)
        self.assertEqual(data["metadata"]["total_entries"], 266)
        self.assertEqual(len(data["anime"]), 219)
        self.assertEqual(len(data["manga"]), 47)

        # Stats checks
        self.assertIn("stats", data)
        stats = data["stats"]
        self.assertEqual(stats["total_entries"], 266)
        self.assertEqual(stats["total_anime"], 219)
        self.assertEqual(stats["total_manga"], 47)
        self.assertGreaterEqual(stats["completed_total"], 227)
        self.assertGreater(stats["mean_anime_score"], 7.0)
        self.assertGreater(stats["mean_manga_score"], 8.0)
        self.assertIsInstance(stats["genres"], list)
        self.assertGreaterEqual(len(stats["genres"]), 10)

    def test_data_js_anime_and_manga_fields(self):
        """Verify all items in data.js contain required presentation fields."""
        content = DATA_JS.read_text(encoding="utf-8")
        match = re.search(r"window\.CATALOG_DATA\s*=\s*(\{.*?\});?\s*$", content, re.DOTALL)
        data = json.loads(match.group(1))

        anime_keys = {"id", "title", "type", "my_score", "my_status", "poster_url", "genres", "studio", "synopsis"}
        for a in data["anime"]:
            missing = anime_keys - set(a.keys())
            self.assertFalse(missing, f"Anime ID {a.get('id')} missing fields: {missing}")
            self.assertIn(a["my_score"], range(11))
            self.assertIsInstance(a["genres"], list)
            self.assertTrue(len(a["poster_url"]) > 0, f"Anime ID {a.get('id')} missing poster")

        manga_keys = {"id", "title", "type", "my_score", "my_status", "poster_url", "genres", "authors", "synopsis"}
        for m in data["manga"]:
            missing = manga_keys - set(m.keys())
            self.assertFalse(missing, f"Manga ID {m.get('id')} missing fields: {missing}")
            self.assertIn(m["my_score"], range(11))
            self.assertIsInstance(m["genres"], list)
            self.assertTrue(len(m["poster_url"]) > 0, f"Manga ID {m.get('id')} missing poster")

    def test_unicode_preservation_in_data_js(self):
        """Verify special Unicode symbols (∬) are preserved without mojibake."""
        content = DATA_JS.read_text(encoding="utf-8")
        match = re.search(r"window\.CATALOG_DATA\s*=\s*(\{.*?\});?\s*$", content, re.DOTALL)
        data = json.loads(match.group(1))

        toubun = next((a for a in data["anime"] if "\u222c" in a["title"]), None)
        self.assertIsNotNone(toubun, "Anime with double integral symbol \u222c not found")
        self.assertEqual(toubun["title"], "5-toubun no Hanayome \u222c")

    def test_index_html_strict_file_protocol_compliance(self):
        """Verify index.html contains no root-relative URLs or external CDN references."""
        html = INDEX_HTML.read_text(encoding="utf-8")

        # 1. No root-relative /paths (e.g. href="/styles.css")
        self.assertNotRegex(
            html,
            r"(href|src)\s*=\s*['\"]\/[a-zA-Z]",
            "index.html must not use root-relative paths for file:// compatibility",
        )

        # 2. No external HTTP(S) CDN scripts or styles
        self.assertNotRegex(
            html,
            r"<script[^>]+src=['\"]https?:\/\/",
            "index.html must not load external CDN scripts (offline requirement)",
        )
        self.assertNotRegex(
            html,
            r"<link[^>]+href=['\"]https?:\/\/",
            "index.html must not load external CDN stylesheets (offline requirement)",
        )

        # 3. Essential relative includes
        self.assertIn('href="styles.css"', html)
        self.assertIn('src="data.js"', html)
        self.assertIn('src="app.js"', html)

    def test_index_html_ui_component_hooks(self):
        """Verify index.html contains all required interactive UI hooks."""
        html = INDEX_HTML.read_text(encoding="utf-8")

        # Controls & Toolbar
        self.assertIn('id="search-input"', html)
        self.assertIn('id="search-clear-btn"', html)
        self.assertIn('id="theme-toggle-btn"', html)
        self.assertIn('id="view-gallery-btn"', html)
        self.assertIn('id="view-table-btn"', html)
        self.assertIn('id="status-select"', html)
        self.assertIn('id="score-select"', html)
        self.assertIn('id="genre-select"', html)
        self.assertIn('id="sort-select"', html)

        # View containers
        self.assertIn('id="gallery-view-container"', html)
        self.assertIn('id="table-view-container"', html)
        self.assertIn('id="empty-state"', html)

        # Drawer / Modal elements
        self.assertIn('id="drawer-backdrop"', html)
        self.assertIn('id="drawer-panel"', html)
        self.assertIn('id="drawer-close-btn"', html)
        self.assertIn('id="drawer-score-my"', html)
        self.assertIn('id="drawer-score-global"', html)
        self.assertIn('id="drawer-mal-btn"', html)

    def test_styles_css_offline_and_design_tokens(self):
        """Verify styles.css is self-contained with no external @import and has design tokens."""
        css = STYLES_CSS.read_text(encoding="utf-8")

        # No external font or CSS @import
        self.assertNotIn("@import url(http", css)
        self.assertNotIn("@import url('http", css)
        self.assertNotIn('@import url("http', css)

        # Design tokens present
        self.assertIn(":root", css)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn("--bg-app", css)
        self.assertIn("--accent-primary", css)
        self.assertIn("--status-completed-bg", css)
        self.assertIn("--score-10-bg", css)
        self.assertIn("--score-master-bg", css)

    def test_app_js_zero_cors_restrictions(self):
        """Verify app.js does not trigger CORS violations under file:// protocol."""
        js = APP_JS.read_text(encoding="utf-8")

        self.assertNotRegex(
            js,
            r"fetch\s*\(\s*['\"]data\.json['\"]",
            "app.js must not fetch('data.json') which fails on file://",
        )
        self.assertNotIn("XMLHttpRequest", js)
        self.assertIn("window.CATALOG_DATA", js)
        self.assertIn("storage", js)  # safe localStorage wrapper


if __name__ == "__main__":
    unittest.main(verbosity=2)
