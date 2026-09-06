"""
Unit and Integration Tests for Data Ingestion & Metadata Enrichment Engine.
Tests parser, safe math, partial dates, multi-tier enricher, atomic cache, and warm run speed.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from pipeline.parser import (
    calculate_progress_pct,
    parse_anime_xml,
    parse_catalog,
    parse_mal_date,
    parse_manga_xml,
    parse_user_info,
    safe_div,
)
from pipeline.enricher import (
    MultiTierEnricher,
    clean_html_text,
    extract_authors,
    extract_studio,
    load_cache,
    normalize_global_score,
    save_cache_atomic,
)


class TestParser(unittest.TestCase):
    """Test suite for XML parsing and normalization logic."""

    def test_parse_mal_date_variations(self):
        # 1. Null / zeroed date
        self.assertIsNone(parse_mal_date("0000-00-00"))
        self.assertIsNone(parse_mal_date("0000-01-00"))
        self.assertIsNone(parse_mal_date(None))
        self.assertIsNone(parse_mal_date(""))
        self.assertIsNone(parse_mal_date("not-a-date"))

        # 2. Year and Month known, Day unknown
        self.assertEqual(parse_mal_date("2021-03-00"), "2021-03")

        # 3. Full ISO date
        self.assertEqual(parse_mal_date("2021-05-01"), "2021-05-01")
        self.assertEqual(parse_mal_date("2021-11-22"), "2021-11-22")

    def test_safe_div(self):
        self.assertEqual(safe_div(10, 2), 5.0)
        self.assertEqual(safe_div(10, 0), 0.0)
        self.assertEqual(safe_div(10, None), 0.0)
        self.assertEqual(safe_div(0, 5), 0.0)

    def test_calculate_progress_pct(self):
        self.assertEqual(calculate_progress_pct(5, 10), 50.0)
        self.assertEqual(calculate_progress_pct(12, 12), 100.0)
        self.assertEqual(calculate_progress_pct(15, 12), 100.0)  # Capped at 100%
        self.assertEqual(calculate_progress_pct(0, 0), 0.0)      # Safe against 0
        self.assertEqual(calculate_progress_pct(5, 0), 0.0)      # Safe against 0

    def test_parse_anime_xml_count_and_schema(self):
        anime_items = parse_anime_xml("animelist_1788635141_-_7821911.xml.gz")
        self.assertEqual(len(anime_items), 219, "Must parse exactly 219 anime entries")

        # Verify schema compliance
        required_keys = {
            "id", "title", "title_japanese", "synonyms", "type",
            "episodes", "my_watched_episodes", "my_score", "my_status",
            "my_start_date", "my_finish_date", "poster_url", "genres",
            "studio", "synopsis", "global_score", "mal_url",
        }
        for item in anime_items:
            for k in required_keys:
                self.assertIn(k, item, f"Missing key {k} in anime item")
            self.assertIsInstance(item["id"], int)
            self.assertGreater(item["id"], 0)
            self.assertIsInstance(item["my_score"], int)
            self.assertTrue(0 <= item["my_score"] <= 10)

    def test_parse_manga_xml_count_and_schema(self):
        manga_items = parse_manga_xml("mangalist_1788635144_-_7821911.xml.gz")
        self.assertEqual(len(manga_items), 47, "Must parse exactly 47 manga entries")

        # Verify schema compliance
        required_keys = {
            "id", "title", "title_japanese", "synonyms", "type",
            "chapters", "volumes", "my_read_chapters", "my_read_volumes",
            "my_score", "my_status", "my_start_date", "my_finish_date",
            "poster_url", "genres", "authors", "synopsis", "global_score", "mal_url",
        }
        for item in manga_items:
            for k in required_keys:
                self.assertIn(k, item, f"Missing key {k} in manga item")
            self.assertIsInstance(item["id"], int)
            self.assertGreater(item["id"], 0)
            self.assertIsInstance(item["my_score"], int)
            self.assertTrue(0 <= item["my_score"] <= 10)

    def test_parse_catalog(self):
        anime, manga, meta = parse_catalog()
        self.assertEqual(len(anime), 219)
        self.assertEqual(len(manga), 47)
        self.assertEqual(meta["total_entries"], 266)
        self.assertEqual(meta["user_name"], "hazza_bhaskara")
        self.assertEqual(meta["user_id"], 7821911)

    def test_unicode_titles_preserved(self):
        anime, _, _ = parse_catalog()
        titles = {a["title"] for a in anime}
        self.assertTrue(any("5-toubun no Hanayome ∬" in t for t in titles))
        self.assertTrue(any("Gintama°" in t for t in titles))
        self.assertTrue(any("Kakegurui××" in t for t in titles))
        self.assertTrue(any("Saenai Heroine no Sodatekata ♭" in t for t in titles))
        self.assertTrue(any("Yuru Camp△" in t for t in titles))


class TestEnricher(unittest.TestCase):
    """Test suite for enrichment engine, cache persistence, and warm execution."""

    def test_clean_html_text(self):
        raw = "Hello<br>World &amp; Friends!<p>New paragraph</p><i>Italics</i>"
        cleaned = clean_html_text(raw)
        self.assertEqual(cleaned, "Hello\nWorld & Friends!\n\nNew paragraph\n\nItalics")
        self.assertEqual(clean_html_text(None), "")
        self.assertEqual(clean_html_text(""), "")

    def test_normalize_global_score(self):
        self.assertEqual(normalize_global_score(86, source="anilist"), 8.6)
        self.assertEqual(normalize_global_score(92, source="anilist"), 9.2)
        self.assertEqual(normalize_global_score(8.75, source="jikan"), 8.75)
        self.assertIsNone(normalize_global_score(0))
        self.assertIsNone(normalize_global_score(None))
        self.assertIsNone(normalize_global_score("invalid"))

    def test_extract_authors(self):
        staff = {
            "edges": [
                {"role": "Story & Art", "node": {"name": {"full": "Kentarou Miura"}}},
                {"role": "Translator (English)", "node": {"name": {"full": "John Doe"}}},
                {"role": "Art", "node": {"name": {"full": "Studio Gaga"}}},
            ]
        }
        authors = extract_authors(staff)
        self.assertEqual(authors, ["Kentarou Miura", "Studio Gaga"])

    def test_extract_studio(self):
        studios_data = {
            "nodes": [
                {"name": "Sunrise"},
                {"name": "Bandai Visual"},
            ]
        }
        primary, all_s = extract_studio(studios_data)
        self.assertEqual(primary, "Sunrise")
        self.assertEqual(all_s, ["Sunrise", "Bandai Visual"])

    def test_extract_studio_fallback(self):
        # 1. Existing behavior preserved when nodes exist
        studios_data = {"nodes": [{"name": "Sunrise"}, {"name": "Bandai Visual"}]}
        primary, all_s = extract_studio(studios_data, default="Unknown")
        self.assertEqual(primary, "Sunrise")
        self.assertEqual(all_s, ["Sunrise", "Bandai Visual"])

        # 2. Empty nodes with fallback
        primary, all_s = extract_studio({"nodes": []}, default="Natural High")
        self.assertEqual(primary, "Natural High")
        self.assertEqual(all_s, ["Natural High"])

        # 3. None with default
        primary, all_s = extract_studio(None, default="Unknown")
        self.assertEqual(primary, "Unknown")
        self.assertEqual(all_s, ["Unknown"])

    def test_atomic_cache_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_cache_file = Path(tmpdir) / "test_cache.json"
            data = {"anime:1": {"title": "Cowboy Bebop", "poster_url": "http://img.png", "genres": ["Action"], "synopsis": "Test"}}
            save_cache_atomic(data, test_cache_file)

            # Confirm file exists and is valid JSON
            self.assertTrue(test_cache_file.exists())
            loaded = load_cache(test_cache_file)
            self.assertEqual(loaded, data)

    def test_tier5_fallback(self):
        enricher = MultiTierEnricher(offline=True)
        dummy_item = {"id": 999999, "title": "Dummy Offline Show"}
        fallback = enricher.tier5_local_synthetic_fallback(dummy_item, "anime")
        self.assertEqual(fallback["mal_id"], 999999)
        self.assertEqual(fallback["source"], "fallback_xml")
        self.assertTrue(fallback["poster_url"].startswith("data:image/svg+xml"))
        self.assertEqual(fallback["genres"], ["Uncategorized"])

    def test_cache_completeness_and_warm_speed(self):
        cache_path = Path("metadata_cache.json")
        self.assertTrue(cache_path.exists(), "metadata_cache.json must exist")
        cache = load_cache(cache_path)
        self.assertEqual(len(cache), 266, "Cache must contain exactly 266 entries")

        anime, manga, _ = parse_catalog()

        # Measure warm run speed
        t0 = time.time()
        enricher = MultiTierEnricher(cache_path=cache_path)
        en_anime, en_manga = enricher.enrich_catalog(anime, manga)
        duration = time.time() - t0

        self.assertLess(duration, 0.20, f"Warm run took {duration:.4f}s; expected < 0.20s")

        # Verify every item has enriched poster, genres, synopsis, studio/authors
        for a in en_anime:
            self.assertTrue(a["poster_url"], f"Anime {a['id']} has no poster_url")
            self.assertTrue(len(a["genres"]) > 0, f"Anime {a['id']} has no genres")
            self.assertTrue(bool(a.get("studio")), f"Anime {a['id']} has empty studio")
            self.assertTrue(a["synopsis"], f"Anime {a['id']} has no synopsis")

        for m in en_manga:
            self.assertTrue(m["poster_url"], f"Manga {m['id']} has no poster_url")
            self.assertTrue(len(m["genres"]) > 0, f"Manga {m['id']} has no genres")
            self.assertTrue(bool(m.get("authors")), f"Manga {m['id']} has empty authors")
            self.assertTrue(m["synopsis"], f"Manga {m['id']} has no synopsis")


if __name__ == "__main__":
    unittest.main()
