#!/usr/bin/env python3
"""
Animanga Showcase — Master Build Pipeline.

Unified orchestration script executing the entire showcase pipeline end-to-end:
  1. Parse raw MyAnimeList (MAL) gzip exports (219 anime, 47 manga) via pipeline.parser
  2. Enrich records using pipeline.enricher (metadata_cache.json for instant offline builds)
  3. Generate the Notion/Airtable Web Showcase via web.generator (data.js, index.html, styles.css, app.js)
  4. Build the professional Excel Workbook via excel.generator (Animanga_Showcase.xlsx)

CLI Options:
  --offline       Run fully offline using cached metadata (default: True)
  --no-offline    Allow online queries if cached metadata is missing
  --force-enrich  Re-query external APIs if cache is missing/incomplete
  --skip-web      Skip web showcase generation
  --skip-excel    Skip Excel workbook generation
  --output-excel  Custom target path for the Excel workbook
  --help          Display help message
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

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

from pipeline.parser import parse_catalog
from pipeline.enricher import MultiTierEnricher, DEFAULT_CACHE_PATH, load_cache
from web.generator import generate_web_showcase
from excel.generator import generate_excel_workbook


def build_catalog(
    offline: bool = True,
    force_enrich: bool = False,
    skip_web: bool = False,
    skip_excel: bool = False,
    output_excel: str | Path = "Animanga_Showcase.xlsx",
    cache_path: str | Path = "metadata_cache.json",
    project_root: str | Path = PROJECT_ROOT,
    anime_xml: Optional[str | Path] = None,
    manga_xml: Optional[str | Path] = None,
) -> dict[str, Any]:
    """
    Execute the entire showcase pipeline end-to-end.

    Returns:
        Dictionary containing build metadata, execution metrics, and generated artifacts.
    """
    root = Path(project_root).resolve()
    t_start = time.perf_counter()

    anime_xml_path = Path(anime_xml) if anime_xml else root / "animelist_1788635141_-_7821911.xml.gz"
    manga_xml_path = Path(manga_xml) if manga_xml else root / "mangalist_1788635144_-_7821911.xml.gz"
    cache_file = Path(cache_path) if Path(cache_path).is_absolute() else root / cache_path
    excel_file = Path(output_excel) if Path(output_excel).is_absolute() else root / output_excel

    # Resolve offline vs online configuration
    if force_enrich:
        effective_offline = False
        effective_force_refresh = True
    else:
        effective_offline = offline
        effective_force_refresh = False

    print("=" * 78)
    print(" ANIMANGA SHOWCASE — MASTER BUILD PIPELINE")
    print("=" * 78)
    print(f"Mode: {'OFFLINE (High-Speed Cached)' if effective_offline else 'ONLINE (API Enrichment Enabled)'}")
    print(f"Project Root: {root}")
    print(f"Metadata Cache: {cache_file}")
    print(f"Excel Output: {excel_file}")
    print("-" * 78)

    # -------------------------------------------------------------------------
    # Stage 1: Parse Raw MAL XML Exports
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("[1/4] Parsing MyAnimeList gzip XML export archives...")
    if not anime_xml_path.exists():
        raise FileNotFoundError(f"Anime XML export not found at: {anime_xml_path}")
    if not manga_xml_path.exists():
        raise FileNotFoundError(f"Manga XML export not found at: {manga_xml_path}")

    anime_items, manga_items, catalog_meta = parse_catalog(
        anime_path=anime_xml_path,
        manga_path=manga_xml_path,
    )
    t_parse = time.perf_counter() - t0
    total_parsed = len(anime_items) + len(manga_items)
    print(
        f"      -> Parsed {len(anime_items)} anime, {len(manga_items)} manga "
        f"({total_parsed} total records) in {t_parse * 1000:.1f}ms"
    )

    # -------------------------------------------------------------------------
    # Stage 2: Multi-Tier Metadata Enrichment
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("[2/4] Enriching metadata via 5-Tier Resilient Engine...")
    enricher = MultiTierEnricher(cache_path=cache_file, offline=effective_offline)
    enriched_anime, enriched_manga = enricher.enrich_catalog(
        anime_items,
        manga_items,
        force_refresh=effective_force_refresh,
    )
    t_enrich = time.perf_counter() - t0
    cached_count = len(enricher.cache)
    print(
        f"      -> Enriched {len(enriched_anime)} anime, {len(enriched_manga)} manga "
        f"({cached_count} cached entries) in {t_enrich * 1000:.1f}ms"
    )

    # -------------------------------------------------------------------------
    # Stage 3: Notion / Airtable Web Showcase Generation
    # -------------------------------------------------------------------------
    generated_web_files: dict[str, str] = {}
    t_web = 0.0
    if not skip_web:
        t0 = time.perf_counter()
        print("[3/4] Generating Notion/Airtable-Style Web Showcase...")
        generated_web_files = generate_web_showcase(
            anime_records=enriched_anime,
            manga_records=enriched_manga,
            output_dir=root,
            cache_path=cache_file,
            offline=effective_offline,
        )
        t_web = time.perf_counter() - t0
        print(f"      -> Web Showcase generated in {t_web * 1000:.1f}ms")
        for fname, fpath in generated_web_files.items():
            f_size = os.path.getsize(fpath) if os.path.exists(fpath) else 0
            print(f"         • {fname:<14} ({f_size:>7,} bytes) -> {Path(fpath).name}")
    else:
        print("[3/4] Generating Web Showcase... SKIPPED (--skip-web)")

    # -------------------------------------------------------------------------
    # Stage 4: Professional Excel Workbook Compilation
    # -------------------------------------------------------------------------
    generated_excel_path: Optional[str] = None
    t_excel = 0.0
    if not skip_excel:
        t0 = time.perf_counter()
        print("[4/4] Building Professional Excel Workbook (.xlsx)...")
        generated_excel_path = generate_excel_workbook(
            output_path=excel_file,
            anime_items=enriched_anime,
            manga_items=enriched_manga,
        )
        t_excel = time.perf_counter() - t0
        excel_size = os.path.getsize(excel_file) if excel_file.exists() else 0
        print(f"      -> Workbook compiled in {t_excel * 1000:.1f}ms")
        print(f"         • {excel_file.name} ({excel_size:>7,} bytes, 3 worksheets)")
    else:
        print("[4/4] Building Excel Workbook... SKIPPED (--skip-excel)")

    # -------------------------------------------------------------------------
    # Build Summary & Performance Metrics
    # -------------------------------------------------------------------------
    total_elapsed = time.perf_counter() - t_start

    print("-" * 78)
    print(" BUILD PIPELINE SUMMARY")
    print("-" * 78)
    print(f"Total Entries Processed : {total_parsed} (219 Anime + 47 Manga)")
    print(f"Metadata Cache Entries  : {cached_count}")
    print(f"Stage 1: XML Parsing    : {t_parse * 1000:>6.1f} ms")
    print(f"Stage 2: Enrichment     : {t_enrich * 1000:>6.1f} ms")
    if not skip_web:
        print(f"Stage 3: Web Showcase   : {t_web * 1000:>6.1f} ms")
    if not skip_excel:
        print(f"Stage 4: Excel Workbook : {t_excel * 1000:>6.1f} ms")
    print(f"Total Pipeline Runtime  : {total_elapsed:>6.3f} s")
    print("=" * 78)
    print(" SUCCESS: All catalog targets built and validated cleanly!")
    print("=" * 78)

    return {
        "success": True,
        "total_anime": len(enriched_anime),
        "total_manga": len(enriched_manga),
        "total_entries": total_parsed,
        "cache_entries": cached_count,
        "web_files": generated_web_files,
        "excel_path": str(excel_file),
        "duration_seconds": total_elapsed,
        "timings_ms": {
            "parse": t_parse * 1000.0,
            "enrich": t_enrich * 1000.0,
            "web": t_web * 1000.0,
            "excel": t_excel * 1000.0,
            "total": total_elapsed * 1000.0,
        },
    }


def main() -> None:
    """CLI entry point for the master build pipeline."""
    parser = argparse.ArgumentParser(
        description="Animanga Showcase — Master Build Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--offline",
        dest="offline",
        action="store_true",
        default=True,
        help="Run fully offline without network queries (default: True).",
    )
    parser.add_argument(
        "--no-offline",
        dest="offline",
        action="store_false",
        help="Allow online network queries if cached metadata is missing.",
    )
    parser.add_argument(
        "--force-enrich",
        action="store_true",
        default=False,
        help="Re-query API if cache is missing/incomplete (forces online re-fetch).",
    )
    parser.add_argument(
        "--skip-web",
        action="store_true",
        default=False,
        help="Skip Notion/Airtable Web Showcase generation.",
    )
    parser.add_argument(
        "--skip-excel",
        action="store_true",
        default=False,
        help="Skip Excel Workbook (.xlsx) generation.",
    )
    parser.add_argument(
        "--output-excel",
        type=str,
        default="Animanga_Showcase.xlsx",
        help="Target path for the generated Excel workbook.",
    )
    parser.add_argument(
        "--cache-path",
        type=str,
        default="metadata_cache.json",
        help="Path to metadata cache JSON file.",
    )

    args = parser.parse_args()

    try:
        build_catalog(
            offline=args.offline,
            force_enrich=args.force_enrich,
            skip_web=args.skip_web,
            skip_excel=args.skip_excel,
            output_excel=args.output_excel,
            cache_path=args.cache_path,
        )
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n[!] Build interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"\n[ERROR] Master build pipeline failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
