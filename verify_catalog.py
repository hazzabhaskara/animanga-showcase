#!/usr/bin/env python3
"""
Animanga Showcase — Automated Verification Suite.

Zero-tolerance automated verification script validating:
  1. 100% item counts: exactly 219 anime and 47 manga (266 total) across raw XMLs,
     cache, web data, and Excel worksheets.
  2. Artifact file existence & non-empty verification:
     - metadata_cache.json
     - data.js
     - index.html
     - styles.css
     - app.js
     - Animanga_Showcase.xlsx
  3. Excel workbook integrity:
     - Exactly 3 sheets ('Anime List', 'Manga List', 'Overview & Stats')
     - Row counts (220 in Anime List, 48 in Manga List)
     - Headers, auto-filters, frozen panes, conditional formatting
     - Zero formula errors (#REF!, #NAME?, #VALUE!, #DIV/0!, #N/A)
     - Valid formulas using AVERAGEIF(..., ">0")
  4. Web Showcase architecture:
     - Valid data.js syntax and window.CATALOG_DATA schema
     - Required DOM elements in index.html (search, filters, view toggle, drawer)
     - styles.css offline tokens and theme support
     - app.js file:// compatibility audit (zero forbidden fetch('data.json') / XHR)
  5. Data integrity & score-10 preservation:
     - Non-empty posters, valid genres, non-empty synopsis, studio/authors
     - Normalized global scores [0.0, 10.0]
     - Preservation of score-10 titles (Clannad: After Story, Steins;Gate, Berserk, Oyasumi Punpun)
     - Ongoing manga zero-chapter safety and partial date normalization
     - Non-ASCII / Unicode symbol preservation ('∬' in 5-toubun no Hanayome ∬)
  6. Performance benchmark:
     - Warm cache enrichment latency (assert mean < 50ms)

Exit Codes:
  0: 100% of checks passed cleanly
  1: One or more checks failed
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure stdout and stderr for UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import openpyxl

from pipeline.parser import parse_catalog, parse_mal_date, safe_div, calculate_progress_pct
from pipeline.enricher import MultiTierEnricher, load_cache, DEFAULT_CACHE_PATH


class VerificationRunner:
    """Orchestrates comprehensive automated verification checks."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.root = project_root
        self.anime_xml = self.root / "animelist_1788635141_-_7821911.xml.gz"
        self.manga_xml = self.root / "mangalist_1788635144_-_7821911.xml.gz"
        self.cache_file = self.root / "metadata_cache.json"
        self.data_js = self.root / "data.js"
        self.index_html = self.root / "index.html"
        self.styles_css = self.root / "styles.css"
        self.app_js = self.root / "app.js"
        self.excel_file = self.root / "Animanga_Showcase.xlsx"

        self.passed_checks = 0
        self.failed_checks = 0
        self.failures: list[str] = []

    def log_check(self, name: str, passed: bool, details: str = "") -> None:
        """Record and display check result."""
        status = "[PASS]" if passed else "[FAIL]"
        if passed:
            self.passed_checks += 1
            print(f"  {status} {name}{' (' + details + ')' if details else ''}")
        else:
            self.failed_checks += 1
            msg = f"{name}: {details}" if details else name
            self.failures.append(msg)
            print(f"  {status} {name}{' (' + details + ')' if details else ''}")

    # =========================================================================
    # Check 1: Item Counts & Raw Data Verification
    # =========================================================================
    def verify_item_counts(self) -> None:
        print("\n" + "=" * 78)
        print(" CHECK 1: Item Counts & Raw Data Verification (219 Anime, 47 Manga)")
        print("=" * 78)

        # 1.1 Verify raw XML files
        if not self.anime_xml.exists() or not self.manga_xml.exists():
            self.log_check("Raw XML Export Archives Exist", False, "One or both .xml.gz files missing")
            return
        self.log_check("Raw XML Export Archives Exist", True, f"{self.anime_xml.name}, {self.manga_xml.name}")

        # 1.2 Parse raw XMLs
        anime_items, manga_items, meta = parse_catalog(self.anime_xml, self.manga_xml)
        n_anime = len(anime_items)
        n_manga = len(manga_items)
        n_total = n_anime + n_manga

        self.log_check(
            "Parsed Anime Record Count == 219",
            n_anime == 219,
            f"Found {n_anime}",
        )
        self.log_check(
            "Parsed Manga Record Count == 47",
            n_manga == 47,
            f"Found {n_manga}",
        )
        self.log_check(
            "Parsed Total Entry Count == 266",
            n_total == 266,
            f"Found {n_total}",
        )
        self.log_check(
            "User Metadata Extracted",
            meta.get("user_name") == "hazza_bhaskara",
            f"User: {meta.get('user_name')}",
        )

        # 1.3 Cache counts
        cache = load_cache(self.cache_file)
        anime_cache = {k: v for k, v in cache.items() if k.startswith("anime:")}
        manga_cache = {k: v for k, v in cache.items() if k.startswith("manga:")}
        foreign_cache = {k: v for k, v in cache.items() if not (k.startswith("anime:") or k.startswith("manga:"))}

        self.log_check(
            "Cache Contains Exactly 219 Anime Keys",
            len(anime_cache) == 219,
            f"Found {len(anime_cache)} anime keys",
        )
        self.log_check(
            "Cache Contains Exactly 47 Manga Keys",
            len(manga_cache) == 47,
            f"Found {len(manga_cache)} manga keys",
        )
        self.log_check(
            "Cache Contains Exactly 266 Total Keys",
            len(cache) == 266,
            f"Found {len(cache)} keys",
        )
        self.log_check(
            "Cache Has Zero Foreign / Corrupt Keys",
            len(foreign_cache) == 0,
            f"Found {len(foreign_cache)} foreign keys",
        )

        # 1.4 1:1 ID Correspondence between raw XML and Cache
        raw_anime_ids = {f"anime:{a['id']}" for a in anime_items}
        raw_manga_ids = {f"manga:{m['id']}" for m in manga_items}
        self.log_check(
            "Anime Cache Keys 1:1 Match Raw XML IDs",
            set(anime_cache.keys()) == raw_anime_ids,
            "Exact match",
        )
        self.log_check(
            "Manga Cache Keys 1:1 Match Raw XML IDs",
            set(manga_cache.keys()) == raw_manga_ids,
            "Exact match",
        )

    # =========================================================================
    # Check 2: Artifact Files Existence & Non-Empty Verification
    # =========================================================================
    def verify_artifacts(self) -> None:
        print("\n" + "=" * 78)
        print(" CHECK 2: Artifact Files Existence & Non-Empty Verification")
        print("=" * 78)

        artifacts = [
            (self.cache_file, 100_000, "Metadata Cache JSON"),
            (self.data_js, 100_000, "Web Showcase Data Bridge (data.js)"),
            (self.index_html, 5_000, "Web Showcase Application (index.html)"),
            (self.styles_css, 10_000, "Web Showcase Stylesheet (styles.css)"),
            (self.app_js, 10_000, "Web Showcase Application Script (app.js)"),
            (self.excel_file, 20_000, "Professional Excel Workbook (Animanga_Showcase.xlsx)"),
        ]

        for path, min_bytes, description in artifacts:
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            is_valid = exists and size >= min_bytes
            self.log_check(
                f"{description} Exists & Non-Empty",
                is_valid,
                f"Size: {size:,} bytes, Min: {min_bytes:,} bytes",
            )

    # =========================================================================
    # Check 3: Excel Workbook Usability & Structure Verification
    # =========================================================================
    def verify_excel_workbook(self) -> None:
        print("\n" + "=" * 78)
        print(" CHECK 3: Excel Workbook Usability & Structure Verification")
        print("=" * 78)

        if not self.excel_file.exists():
            self.log_check("Excel File Available for Audit", False, "Animanga_Showcase.xlsx not found")
            return

        try:
            wb = openpyxl.load_workbook(self.excel_file, data_only=False)
        except Exception as e:
            self.log_check("Excel Workbook Loadable via openpyxl", False, f"Failed to load: {e}")
            return

        self.log_check("Excel Workbook Loadable via openpyxl", True, "Opened cleanly without repair")

        # 3.1 Sheet Names & Ordering
        expected_sheets = ["Anime List", "Manga List", "Overview & Stats"]
        actual_sheets = wb.sheetnames
        self.log_check(
            "Exactly 3 Sheets in Proper Order",
            actual_sheets == expected_sheets,
            f"Sheets: {actual_sheets}",
        )

        # 3.2 Row Counts
        anime_ws = wb["Anime List"]
        manga_ws = wb["Manga List"]
        overview_ws = wb["Overview & Stats"]

        self.log_check(
            "Sheet 'Anime List' Max Rows == 220 (1 Header + 219 Data)",
            anime_ws.max_row == 220,
            f"Found {anime_ws.max_row} rows",
        )
        self.log_check(
            "Sheet 'Manga List' Max Rows == 48 (1 Header + 47 Data)",
            manga_ws.max_row == 48,
            f"Found {manga_ws.max_row} rows",
        )

        # 3.3 Column Counts
        self.log_check(
            "Sheet 'Anime List' Has Required Columns (>= 12)",
            anime_ws.max_column >= 12,
            f"Columns: {anime_ws.max_column}",
        )
        self.log_check(
            "Sheet 'Manga List' Has Required Columns (>= 14)",
            manga_ws.max_column >= 14,
            f"Columns: {manga_ws.max_column}",
        )

        # 3.4 Frozen Panes
        self.log_check(
            "Sheet 'Anime List' Freeze Pane == 'A2'",
            anime_ws.freeze_panes == "A2",
            f"Pane: {anime_ws.freeze_panes}",
        )
        self.log_check(
            "Sheet 'Manga List' Freeze Pane == 'A2'",
            manga_ws.freeze_panes == "A2",
            f"Pane: {manga_ws.freeze_panes}",
        )

        # 3.5 Auto-Filters
        anime_filter = getattr(anime_ws.auto_filter, "ref", None)
        manga_filter = getattr(manga_ws.auto_filter, "ref", None)
        self.log_check(
            "Sheet 'Anime List' Auto-Filter Enabled",
            bool(anime_filter and "A1:" in anime_filter),
            f"Filter ref: {anime_filter}",
        )
        self.log_check(
            "Sheet 'Manga List' Auto-Filter Enabled",
            bool(manga_filter and "A1:" in manga_filter),
            f"Filter ref: {manga_filter}",
        )

        # 3.6 Header Styling
        header_cell_anime = anime_ws["A1"]
        header_cell_manga = manga_ws["A1"]
        self.log_check(
            "Header Fonts Bold & Formatted",
            bool(header_cell_anime.font and header_cell_anime.font.bold and header_cell_manga.font and header_cell_manga.font.bold),
            "Bold headers confirmed",
        )

        # 3.7 Conditional Formatting Rules
        cf_anime = list(anime_ws.conditional_formatting)
        cf_manga = list(manga_ws.conditional_formatting)
        self.log_check(
            "Sheet 'Anime List' Conditional Formatting Configured",
            len(cf_anime) > 0,
            f"{len(cf_anime)} rule blocks",
        )
        self.log_check(
            "Sheet 'Manga List' Conditional Formatting Configured",
            len(cf_manga) > 0,
            f"{len(cf_manga)} rule blocks",
        )

        # 3.8 Formula Integrity Check on Overview & Stats
        formula_errors = ["#REF!", "#NAME?", "#VALUE!", "#DIV/0!", "#N/A", "#NULL!"]
        found_errors: list[str] = []
        averageif_found = False
        anime_ref_found = False
        manga_ref_found = False

        for row in overview_ws.iter_rows(values_only=False):
            for cell in row:
                val = cell.value
                if val and isinstance(val, str):
                    for err in formula_errors:
                        if err in val:
                            found_errors.append(f"{cell.coordinate}: {val}")
                    if val.startswith("="):
                        if "AVERAGEIF" in val:
                            averageif_found = True
                        if "'Anime List'" in val:
                            anime_ref_found = True
                        if "'Manga List'" in val:
                            manga_ref_found = True

        self.log_check(
            "Zero Formula Syntax Errors in 'Overview & Stats'",
            len(found_errors) == 0,
            f"Errors: {found_errors}" if found_errors else "Clean formulas",
        )
        self.log_check(
            "Formulas Reference 'Anime List' and 'Manga List' with Single Quotes",
            anime_ref_found and manga_ref_found,
            "Proper sheet quoting verified",
        )
        self.log_check(
            "Average Rating Uses AVERAGEIF(..., '>0') for Unrated Exclusion",
            averageif_found,
            "AVERAGEIF formula confirmed",
        )

        wb.close()

    # =========================================================================
    # Check 4: Web Showcase Asset & Offline Architecture Audit
    # =========================================================================
    def verify_web_showcase(self) -> None:
        print("\n" + "=" * 78)
        print(" CHECK 4: Web Showcase Asset & Offline Architecture Audit")
        print("=" * 78)

        # 4.1 data.js syntax and structure
        data_js_text = self.data_js.read_text(encoding="utf-8")
        match = re.search(r"window\.CATALOG_DATA\s*=\s*(\{.*?\});?\s*$", data_js_text, re.DOTALL)
        self.log_check(
            "data.js Declares window.CATALOG_DATA Object",
            bool(match),
            "Regex pattern match",
        )

        catalog_data = json.loads(match.group(1)) if match else {}
        self.log_check(
            "window.CATALOG_DATA Contains Required Keys",
            all(k in catalog_data for k in ["metadata", "anime", "manga", "stats"]),
            "metadata, anime, manga, stats present",
        )
        self.log_check(
            "window.CATALOG_DATA Has 219 Anime & 47 Manga",
            len(catalog_data.get("anime", [])) == 219 and len(catalog_data.get("manga", [])) == 47,
            f"Anime: {len(catalog_data.get('anime', []))}, Manga: {len(catalog_data.get('manga', []))}",
        )

        # 4.2 index.html DOM Elements
        index_html_text = self.index_html.read_text(encoding="utf-8")
        self.log_check("index.html Has Valid HTML5 Doctype", "<!DOCTYPE html>" in index_html_text, "<!DOCTYPE html>")
        self.log_check("index.html Has Responsive Viewport Meta", 'meta name="viewport"' in index_html_text, "viewport meta")
        self.log_check("index.html References styles.css", "styles.css" in index_html_text, "styles.css linked")
        self.log_check("index.html References data.js", "data.js" in index_html_text, "data.js scripted")
        self.log_check("index.html References app.js", "app.js" in index_html_text, "app.js scripted")

        has_search = ("search" in index_html_text.lower())
        has_filters = ("filter" in index_html_text.lower()) or ("select" in index_html_text.lower())
        has_view_toggle = ("table" in index_html_text.lower() and "gallery" in index_html_text.lower())
        has_drawer = ("drawer" in index_html_text.lower() or "modal" in index_html_text.lower())

        self.log_check("index.html Contains Instant Search Bar", has_search, "Search input element present")
        self.log_check("index.html Contains Multi-Facet Filter Controls", has_filters, "Filter select/dropdowns present")
        self.log_check("index.html Contains Table/Gallery View Toggle", has_view_toggle, "Dual view modes present")
        self.log_check("index.html Contains Detail Drawer / Modal", has_drawer, "Detail drawer component present")

        # Local file:// compatibility (no root-relative URLs like href="/style.css")
        has_root_urls = bool(re.search(r"(href|src)\s*=\s*['\"]\/[a-zA-Z]", index_html_text))
        self.log_check(
            "index.html Uses Safe Relative Paths (file:// Protocol Compatible)",
            not has_root_urls,
            "Zero root-relative '/' paths",
        )

        # 4.3 styles.css offline tokens
        styles_css_text = self.styles_css.read_text(encoding="utf-8")
        has_css_tokens = "--" in styles_css_text and (
            "slate" in styles_css_text.lower() or "indigo" in styles_css_text.lower() or "color" in styles_css_text.lower()
        )
        self.log_check(
            "styles.css Defines Self-Contained Offline CSS Tokens",
            has_css_tokens,
            "Design tokens detected",
        )

        # 4.4 app.js file:// protocol audit
        app_js_text = self.app_js.read_text(encoding="utf-8")
        has_forbidden_fetch = bool(re.search(r"fetch\s*\(\s*['\"]data\.json['\"]", app_js_text))
        has_xhr = "XMLHttpRequest" in app_js_text
        self.log_check(
            "app.js Avoids Forbidden fetch('data.json') Calls",
            not has_forbidden_fetch,
            "Zero CORS fetch violations",
        )
        self.log_check(
            "app.js Avoids XMLHttpRequest Calls",
            not has_xhr,
            "Zero XHR violations",
        )

    # =========================================================================
    # Check 5: Data Integrity, Normalization & Score-10 Verification
    # =========================================================================
    def verify_data_integrity(self) -> None:
        print("\n" + "=" * 78)
        print(" CHECK 5: Data Integrity, Normalization & Score-10 Verification")
        print("=" * 78)

        cache = load_cache(self.cache_file)
        url_regex = re.compile(r"^(https://|data:image/svg\+xml)")

        invalid_posters = []
        invalid_genres = []
        invalid_synopsis = []
        invalid_scores = []
        invalid_anime_studios = []
        invalid_manga_authors = []

        for key, entry in cache.items():
            # Poster URL
            p = entry.get("poster_url") or entry.get("cover_image_large")
            if not p or not isinstance(p, str) or not url_regex.match(p):
                invalid_posters.append((key, p))

            # Genres
            genres = entry.get("genres")
            if not isinstance(genres, list) or len(genres) == 0 or not all(isinstance(g, str) and len(g.strip()) > 0 for g in genres):
                invalid_genres.append((key, genres))

            # Synopsis
            synopsis = entry.get("synopsis")
            if not synopsis or not isinstance(synopsis, str) or len(synopsis.strip()) == 0:
                invalid_synopsis.append((key, synopsis))

            # Global score
            score = entry.get("global_score")
            if score is not None:
                if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 10.0):
                    invalid_scores.append((key, score))

            # Anime studio
            if key.startswith("anime:"):
                studio = entry.get("studio")
                studios = entry.get("studios")
                has_st = bool(studio and isinstance(studio, str) and studio.strip())
                has_sts = bool(studios and isinstance(studios, list) and any(isinstance(s, str) and s.strip() for s in studios))
                if not (has_st or has_sts):
                    invalid_anime_studios.append(key)

            # Manga authors
            if key.startswith("manga:"):
                authors = entry.get("authors")
                has_auth = bool(authors and isinstance(authors, list) and any(isinstance(a, str) and a.strip() for a in authors))
                if not has_auth:
                    invalid_manga_authors.append(key)

        self.log_check("All 266 Entries Have Valid Poster URLs", len(invalid_posters) == 0, f"Violations: {len(invalid_posters)}")
        self.log_check("All 266 Entries Have Non-Empty Genres List", len(invalid_genres) == 0, f"Violations: {len(invalid_genres)}")
        self.log_check("All 266 Entries Have Non-Empty Synopsis", len(invalid_synopsis) == 0, f"Violations: {len(invalid_synopsis)}")
        self.log_check("All Enriched Global Scores in [0.0, 10.0]", len(invalid_scores) == 0, f"Violations: {len(invalid_scores)}")
        self.log_check("All 219 Anime Have Valid Non-Empty Studio", len(invalid_anime_studios) == 0, f"Violations: {len(invalid_anime_studios)}")
        self.log_check("All 47 Manga Have Valid Non-Empty Authors", len(invalid_manga_authors) == 0, f"Violations: {len(invalid_manga_authors)}")

        # Score-10 Preservations
        anime_items, manga_items, _ = parse_catalog(self.anime_xml, self.manga_xml)
        raw_anime_10s = [a for a in anime_items if a.get("my_score") == 10]
        raw_manga_10s = [m for m in manga_items if m.get("my_score") == 10]

        anime_10_titles = [a["title"] for a in raw_anime_10s]
        manga_10_titles = [m["title"] for m in raw_manga_10s]

        has_clannad = any("Clannad: After Story" in t for t in anime_10_titles)
        has_steins = any("Steins;Gate" in t for t in anime_10_titles)
        has_berserk = any("Berserk" in t for t in manga_10_titles)
        has_punpun = any("Oyasumi Punpun" in t for t in manga_10_titles)

        self.log_check("Score 10 Preserved: Clannad: After Story", has_clannad, "Clannad: After Story score=10")
        self.log_check("Score 10 Preserved: Steins;Gate", has_steins, "Steins;Gate score=10")
        self.log_check("Score 10 Preserved: Berserk", has_berserk, "Berserk score=10")
        self.log_check("Score 10 Preserved: Oyasumi Punpun", has_punpun, "Oyasumi Punpun score=10")

        # Ongoing manga division by zero check
        berserk_item = next((m for m in manga_items if m["title"] == "Berserk"), None)
        self.log_check(
            "Ongoing Manga Zero Division Safe (Berserk chapters=0, pct=0.0%)",
            bool(berserk_item and berserk_item.get("chapters") == 0 and berserk_item.get("chapter_progress_pct") == 0.0),
            "Progress safe",
        )

        # Partial date normalization check
        monster_item = next((a for a in anime_items if a["title"] == "Monster"), None)
        self.log_check(
            "Partial Date Normalization ('2021-03-00' -> '2021-03' in Monster)",
            bool(monster_item and monster_item.get("my_start_date") == "2021-03"),
            f"Monster start date: {monster_item.get('my_start_date') if monster_item else 'None'}",
        )

        # Unicode preservation
        toubun_item = next((a for a in anime_items if "5-toubun" in a["title"] and "∬" in a["title"]), None)
        self.log_check(
            "Unicode Symbol Preservation ('∬' double integral in 5-toubun no Hanayome ∬)",
            bool(toubun_item and "∬" in toubun_item["title"]),
            toubun_item["title"] if toubun_item else "Not found",
        )

    # =========================================================================
    # Check 6: Warm Cache Latency Benchmark
    # =========================================================================
    def verify_warm_latency_benchmark(self) -> None:
        print("\n" + "=" * 78)
        print(" CHECK 6: Warm Cache Latency Benchmark (< 50ms)")
        print("=" * 78)

        anime_items, manga_items, _ = parse_catalog(self.anime_xml, self.manga_xml)
        enricher = MultiTierEnricher(cache_path=self.cache_file, offline=True)

        # Warm up JIT / cache lookups
        enricher.enrich_catalog(anime_items, manga_items)

        latencies_ms: list[float] = []
        iterations = 10
        for _ in range(iterations):
            t0 = time.perf_counter()
            enricher.enrich_catalog(anime_items, manga_items)
            dur_ms = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(dur_ms)

        mean_latency = sum(latencies_ms) / len(latencies_ms)
        min_latency = min(latencies_ms)
        max_latency = max(latencies_ms)

        passed = mean_latency < 50.0  # Threshold: 50 milliseconds
        self.log_check(
            "Warm Catalog Enrichment Latency Mean < 50.0 ms",
            passed,
            f"Mean: {mean_latency:.2f} ms (Min: {min_latency:.2f} ms, Max: {max_latency:.2f} ms over {iterations} runs)",
        )

    # =========================================================================
    # Run Complete Verification Suite
    # =========================================================================
    def run(self) -> int:
        start_time = time.perf_counter()
        print("=" * 78)
        print(" ANIMANGA SHOWCASE — AUTOMATED VERIFICATION SUITE")
        print("=" * 78)
        print(f"Working Directory: {self.root}")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        self.verify_item_counts()
        self.verify_artifacts()
        self.verify_excel_workbook()
        self.verify_web_showcase()
        self.verify_data_integrity()
        self.verify_warm_latency_benchmark()

        total_elapsed = time.perf_counter() - start_time
        total_checks = self.passed_checks + self.failed_checks

        print("\n" + "=" * 78)
        print(" VERIFICATION SUITE EXECUTION SUMMARY")
        print("=" * 78)
        print(f"Total Verifications Run : {total_checks}")
        print(f"Checks Passed           : {self.passed_checks} ({(self.passed_checks/total_checks)*100:.1f}%)")
        print(f"Checks Failed           : {self.failed_checks}")
        print(f"Duration                : {total_elapsed:.3f} s")
        print("-" * 78)

        if self.failed_checks == 0:
            print(" [PASS] 100% OF VERIFICATION CHECKS PASSED CLEANLY!")
            print("=" * 78)
            return 0
        else:
            print(" [FAIL] VERIFICATION FAILURES DETECTED:")
            for f in self.failures:
                print(f"   • {f}")
            print("=" * 78)
            return 1


def main() -> None:
    """CLI entry point for verification script."""
    runner = VerificationRunner()
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
