"""
Animanga Showcase — Web Showcase Generator.

Generates the interactive Notion/Airtable-style web showcase artifacts:
  - data.js (window.CATALOG_DATA data bridge conforming to PROJECT.md)
  - index.html (Notion/Airtable single-page app)
  - styles.css (Self-contained CSS with light/dark design tokens)
  - app.js (Sub-100ms in-memory search, filtering, and detail drawer)

Guarantees 100% offline functionality over the file:// protocol.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.parser import parse_catalog
from pipeline.enricher import MultiTierEnricher, load_cache, DEFAULT_CACHE_PATH


def calculate_catalog_stats(
    anime_items: list[dict[str, Any]],
    manga_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate comprehensive statistics across both anime and manga datasets."""
    all_items = anime_items + manga_items

    total_anime = len(anime_items)
    total_manga = len(manga_items)
    total_entries = total_anime + total_manga

    completed_anime = sum(1 for a in anime_items if a.get("my_status") == "Completed")
    completed_manga = sum(1 for m in manga_items if m.get("my_status") == "Completed")
    completed_total = completed_anime + completed_manga

    # Scores (strictly exclude 0 unrated for mean rating)
    anime_scores = [a["my_score"] for a in anime_items if a.get("my_score", 0) > 0]
    manga_scores = [m["my_score"] for m in manga_items if m.get("my_score", 0) > 0]
    all_scores = anime_scores + manga_scores

    mean_anime_score = round(sum(anime_scores) / len(anime_scores), 2) if anime_scores else 0.0
    mean_manga_score = round(sum(manga_scores) / len(manga_scores), 2) if manga_scores else 0.0
    mean_total_score = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0

    total_episodes_watched = sum(a.get("my_watched_episodes", 0) for a in anime_items)
    total_chapters_read = sum(m.get("my_read_chapters", 0) for m in manga_items)

    # Unique genres
    genres_set: set[str] = set()
    for item in all_items:
        for g in item.get("genres", []):
            if g and isinstance(g, str):
                genres_set.add(g)
    genres_list = sorted(genres_set)

    # Unique studios (anime)
    studios_set: set[str] = set()
    for a in anime_items:
        s = a.get("studio")
        if s and s != "Unknown":
            studios_set.add(s)
    studios_list = sorted(studios_set)

    # Unique authors (manga)
    authors_set: set[str] = set()
    for m in manga_items:
        for author in m.get("authors", []):
            if author and isinstance(author, str):
                authors_set.add(author)
    authors_list = sorted(authors_set)

    # Status distribution
    status_counts: dict[str, int] = {}
    for item in all_items:
        st = item.get("my_status", "Unknown")
        status_counts[st] = status_counts.get(st, 0) + 1

    # Score distribution (0 to 10)
    score_counts: dict[int, int] = {score: 0 for score in range(11)}
    for item in all_items:
        sc = item.get("my_score", 0)
        score_counts[sc] = score_counts.get(sc, 0) + 1

    return {
        "total_entries": total_entries,
        "total_anime": total_anime,
        "total_manga": total_manga,
        "completed_anime": completed_anime,
        "completed_manga": completed_manga,
        "completed_total": completed_total,
        "mean_anime_score": mean_anime_score,
        "mean_manga_score": mean_manga_score,
        "mean_total_score": mean_total_score,
        "total_episodes_watched": total_episodes_watched,
        "total_chapters_read": total_chapters_read,
        "genres": genres_list,
        "studios": studios_list,
        "authors": authors_list,
        "status_distribution": status_counts,
        "score_distribution": score_counts,
    }


def prepare_web_items(
    anime_items: list[dict[str, Any]],
    manga_items: list[dict[str, Any]],
    cache_data: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Format and enhance anime and manga items with cached rich metadata
    for flawless rendering in web tables and gallery cards.
    """
    prepared_anime: list[dict[str, Any]] = []
    for a in anime_items:
        mal_id = a["id"]
        cache_key = f"anime:{mal_id}"
        cached = cache_data.get(cache_key, {})

        title_eng = cached.get("title_english") or ""
        title_jp = a.get("title_japanese") or cached.get("title_japanese") or ""
        banner = cached.get("banner_image") or ""
        season_year = cached.get("season_year")
        season = cached.get("season")
        format_type = cached.get("format") or a.get("type", "TV")

        item = {
            "id": mal_id,
            "title": a["title"],
            "title_english": title_eng,
            "title_japanese": title_jp,
            "synonyms": a.get("synonyms", []),
            "type": a.get("type", "TV"),
            "format": format_type,
            "episodes": a.get("episodes", 0),
            "my_watched_episodes": a.get("my_watched_episodes", 0),
            "my_score": a.get("my_score", 0),
            "my_status": a.get("my_status", "Plan to Watch"),
            "my_start_date": a.get("my_start_date"),
            "my_finish_date": a.get("my_finish_date"),
            "my_comments": a.get("my_comments", ""),
            "progress_pct": a.get("progress_pct", 0.0),
            "poster_url": a.get("poster_url") or cached.get("poster_url", ""),
            "banner_image": banner,
            "genres": a.get("genres", []),
            "studio": a.get("studio", ""),
            "synopsis": a.get("synopsis") or cached.get("synopsis", ""),
            "global_score": a.get("global_score"),
            "mal_url": a.get("mal_url") or f"https://myanimelist.net/anime/{mal_id}",
            "season_year": season_year,
            "season": season,
        }
        prepared_anime.append(item)

    prepared_manga: list[dict[str, Any]] = []
    for m in manga_items:
        mal_id = m["id"]
        cache_key = f"manga:{mal_id}"
        cached = cache_data.get(cache_key, {})

        title_eng = cached.get("title_english") or ""
        title_jp = m.get("title_japanese") or cached.get("title_japanese") or ""
        banner = cached.get("banner_image") or ""
        format_type = cached.get("format") or m.get("type", "Manga")

        item = {
            "id": mal_id,
            "title": m["title"],
            "title_english": title_eng,
            "title_japanese": title_jp,
            "synonyms": m.get("synonyms", []),
            "type": m.get("type", "Manga"),
            "format": format_type,
            "chapters": m.get("chapters", 0),
            "volumes": m.get("volumes", 0),
            "my_read_chapters": m.get("my_read_chapters", 0),
            "my_read_volumes": m.get("my_read_volumes", 0),
            "my_score": m.get("my_score", 0),
            "my_status": m.get("my_status", "Plan to Read"),
            "my_start_date": m.get("my_start_date"),
            "my_finish_date": m.get("my_finish_date"),
            "my_comments": m.get("my_comments", ""),
            "chapter_progress_pct": m.get("chapter_progress_pct", 0.0),
            "volume_progress_pct": m.get("volume_progress_pct", 0.0),
            "poster_url": m.get("poster_url") or cached.get("poster_url", ""),
            "banner_image": banner,
            "genres": m.get("genres", []),
            "authors": m.get("authors", []),
            "synopsis": m.get("synopsis") or cached.get("synopsis", ""),
            "global_score": m.get("global_score"),
            "mal_url": m.get("mal_url") or f"https://myanimelist.net/manga/{mal_id}",
        }
        prepared_manga.append(item)

    return prepared_anime, prepared_manga


def generate_data_js(
    anime_items: list[dict[str, Any]],
    manga_items: list[dict[str, Any]],
    metadata: dict[str, Any],
    stats: dict[str, Any],
    output_path: Path,
) -> None:
    """Serialize catalog payload into data.js declaring window.CATALOG_DATA."""
    catalog_data = {
        "metadata": {
            "user_name": metadata.get("user_name", "hazza_bhaskara"),
            "export_date": metadata.get("export_date", "2026-09-05T19:05:41Z"),
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total_anime": len(anime_items),
            "total_manga": len(manga_items),
            "total_entries": len(anime_items) + len(manga_items),
        },
        "anime": anime_items,
        "manga": manga_items,
        "stats": stats,
    }

    payload_json = json.dumps(catalog_data, indent=2, ensure_ascii=False)
    js_content = f"// Generated by Animanga Showcase Web Generator\nwindow.CATALOG_DATA = {payload_json};\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(js_content, encoding="utf-8")


def generate_web_showcase(
    anime_records: list[dict[str, Any]] | None = None,
    manga_records: list[dict[str, Any]] | None = None,
    output_dir: str | Path = PROJECT_ROOT,
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    offline: bool = True,
) -> dict[str, str]:
    """
    Generate all web showcase deliverables:
      - data.js
      - index.html
      - styles.css
      - app.js
    Returns dictionary mapping artifact names to their absolute file paths.
    """
    out_dir = Path(output_dir).resolve()
    web_source_dir = Path(__file__).resolve().parent

    # 1. Parse and enrich catalog if not passed
    if anime_records is None or manga_records is None:
        anime_items, manga_items, meta = parse_catalog(
            anime_path=PROJECT_ROOT / "animelist_1788635141_-_7821911.xml.gz",
            manga_path=PROJECT_ROOT / "mangalist_1788635144_-_7821911.xml.gz",
        )
        enricher = MultiTierEnricher(cache_path=PROJECT_ROOT / cache_path, offline=offline)
        anime_records, manga_records = enricher.enrich_catalog(anime_items, manga_items)
    else:
        meta = {
            "user_name": "hazza_bhaskara",
            "export_date": "2026-09-05T19:05:41Z",
            "total_anime": len(anime_records),
            "total_manga": len(manga_records),
            "total_entries": len(anime_records) + len(manga_records),
        }

    # 2. Load cache for additional metadata
    cache_data = load_cache(PROJECT_ROOT / cache_path)

    # 3. Prepare formatted items and stats
    prepared_anime, prepared_manga = prepare_web_items(anime_records, manga_records, cache_data)
    stats = calculate_catalog_stats(prepared_anime, prepared_manga)

    # 4. Emit data.js in target directory (and also inside web/ if different)
    data_js_path = out_dir / "data.js"
    generate_data_js(prepared_anime, prepared_manga, meta, stats, data_js_path)

    if out_dir != web_source_dir:
        web_data_js = web_source_dir / "data.js"
        generate_data_js(prepared_anime, prepared_manga, meta, stats, web_data_js)

    # 5. Ensure index.html, styles.css, app.js are in target directory
    generated_files = {
        "data.js": str(data_js_path),
    }

    for filename in ["index.html", "styles.css", "app.js"]:
        src_file = web_source_dir / filename
        dest_file = out_dir / filename
        if out_dir != web_source_dir and src_file.exists():
            shutil.copy2(src_file, dest_file)
        generated_files[filename] = str(dest_file)

    return generated_files


def main() -> None:
    """CLI entry point for web showcase generator."""
    parser = argparse.ArgumentParser(description="Generate Notion/Airtable Web Showcase for Animanga Catalog.")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT),
        help="Target output directory (defaults to project root).",
    )
    parser.add_argument(
        "--cache-path",
        type=str,
        default=DEFAULT_CACHE_PATH,
        help="Path to metadata_cache.json.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        default=True,
        help="Enforce offline generation using cached metadata.",
    )
    args = parser.parse_args()

    print("=== Animanga Showcase Web Generator ===")
    t0 = datetime.datetime.now()

    files = generate_web_showcase(
        output_dir=args.output_dir,
        cache_path=args.cache_path,
        offline=args.offline,
    )

    duration = (datetime.datetime.now() - t0).total_seconds()
    print(f"Web showcase generated successfully in {duration:.3f}s:")
    for name, path in files.items():
        size = os.path.getsize(path)
        print(f"  - {name}: {path} ({size:,} bytes)")


if __name__ == "__main__":
    main()
