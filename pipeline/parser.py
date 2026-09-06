"""
XML Data Parser & Ingestion Engine for Animanga Showcase.

Ingests MyAnimeList (MAL) gzip XML exports (animelist_*.xml.gz, mangalist_*.xml.gz),
safely parses elements, normalizes schema inconsistencies, handles partial/zero dates,
guards against division by zero on ongoing manga, and outputs clean dictionary data
structures conforming to PROJECT.md § Interface Contracts.
"""

from __future__ import annotations

import gzip
import io
import os
import re
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from typing import Any, BinaryIO, TextIO, Union

# Ensure UTF-8 stdout/stderr encoding on Windows consoles
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


def parse_mal_date(date_str: str | None) -> str | None:
    """
    Safely parse MAL date string (e.g. '0000-00-00', '2021-03-00', '2021-05-01').

    Returns ISO date string (YYYY-MM-DD or YYYY-MM) or None for unentered/invalid dates.
    Guarantees no ValueError exceptions on year 0 or zero month/day.

    Examples:
        >>> parse_mal_date("0000-00-00")
        None
        >>> parse_mal_date("0000-01-00")
        None
        >>> parse_mal_date("2021-03-00")
        '2021-03'
        >>> parse_mal_date("2021-05-01")
        '2021-05-01'
        >>> parse_mal_date(None)
        None
    """
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    if not date_str or date_str == "0000-00-00":
        return None
    parts = date_str.split("-")
    if len(parts) != 3:
        return None
    year, month, day = parts
    # Guard against invalid/zero year
    if year == "0000" or not year.isdigit():
        return None
    # Validate month and day are digits
    if not month.isdigit() or not day.isdigit():
        return None

    if month == "00":
        return year
    if day == "00":
        return f"{year}-{month}"
    return f"{year}-{month}-{day}"


def safe_div(numerator: Union[int, float], denominator: Union[int, float], default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is 0, None, or invalid.
    Protects against division by zero on ongoing manga/anime where totals are 0.
    """
    if denominator is None or denominator == 0:
        return float(default)
    try:
        return float(numerator) / float(denominator)
    except (ZeroDivisionError, TypeError, ValueError):
        return float(default)


def calculate_progress_pct(current: int, total: int) -> float:
    """
    Calculate progress percentage (0.0 to 100.0), safely handling total=0.
    """
    if total is None or total <= 0:
        return 0.0
    val = safe_div(current, total, default=0.0) * 100.0
    return min(100.0, max(0.0, round(val, 1)))


def _read_xml_bytes(source: Union[str, Path, bytes, BinaryIO, TextIO]) -> bytes:
    """Helper to obtain raw UTF-8 XML bytes from various source types."""
    if isinstance(source, bytes):
        raw = source
    elif isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"XML source file not found: {p}")
        with open(p, "rb") as f:
            raw = f.read()
    elif hasattr(source, "read"):
        content = source.read()
        if isinstance(content, str):
            raw = content.encode("utf-8")
        else:
            raw = content
    else:
        raise TypeError(f"Unsupported XML source type: {type(source)}")

    # Decompress if gzipped (magic bytes \x1f\x8b)
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except (gzip.BadGzipFile, zlib.error, EOFError) as e:
            raise gzip.BadGzipFile(f"Corrupted or invalid gzip stream: {e}") from e

    return raw


def load_xml_root(source: Union[str, Path, bytes, BinaryIO, TextIO, ET.Element]) -> ET.Element:
    """
    Load XML root element from a file path, bytes, or file-like object,
    automatically decompressing gzip if necessary. If source is already
    an ET.Element, returns it directly.

    Catches (gzip.BadGzipFile, zlib.error, EOFError) during decompression
    and raises gzip.BadGzipFile with clear diagnostic details.
    """
    if isinstance(source, ET.Element):
        return source
    try:
        raw_bytes = _read_xml_bytes(source)
    except (gzip.BadGzipFile, zlib.error, EOFError) as e:
        if isinstance(e, gzip.BadGzipFile):
            raise
        raise gzip.BadGzipFile(f"Failed to decompress gzip XML stream ({type(e).__name__}): {e}") from e
    return ET.fromstring(raw_bytes)


def parse_user_info(source: Union[str, Path, bytes, BinaryIO, TextIO]) -> dict[str, Any]:
    """
    Extract user metadata from <myinfo> tag in MAL export.
    """
    root = load_xml_root(source)
    myinfo = root.find("myinfo")
    if myinfo is None:
        return {
            "user_id": None,
            "user_name": "unknown",
            "user_export_type": 1,
            "total_anime": 0,
            "total_manga": 0,
        }

    def _get_int(tag: str, default: int = 0) -> int:
        val = myinfo.findtext(tag)
        if val and val.isdigit():
            return int(val)
        return default

    return {
        "user_id": _get_int("user_id"),
        "user_name": myinfo.findtext("user_name", "unknown") or "unknown",
        "user_export_type": _get_int("user_export_type", 1),
        "total_anime": _get_int("user_total_anime", 0),
        "total_watching": _get_int("user_total_watching", 0),
        "total_completed": _get_int("user_total_completed", 0),
        "total_onhold": _get_int("user_total_onhold", 0),
        "total_dropped": _get_int("user_total_dropped", 0),
        "total_plantowatch": _get_int("user_total_plantowatch", 0),
        "total_manga": _get_int("user_total_manga", 0),
        "total_reading": _get_int("user_total_reading", 0),
        "total_plantoread": _get_int("user_total_plantoread", 0),
    }


def parse_anime_xml(source: Union[str, Path, bytes, BinaryIO, TextIO]) -> list[dict[str, Any]]:
    """
    Parse MAL anime XML export into normalized AnimeItem dictionaries
    conforming to PROJECT.md § Interface Contracts.

    Total expected records: 219.
    """
    root = load_xml_root(source)
    items: list[dict[str, Any]] = []

    for el in root.findall("anime"):
        mal_id_str = el.findtext("series_animedb_id", "0")
        mal_id = int(mal_id_str) if mal_id_str and mal_id_str.isdigit() else 0

        title = el.findtext("series_title") or ""
        series_type = el.findtext("series_type") or "TV"

        episodes_str = el.findtext("series_episodes", "0")
        episodes = int(episodes_str) if episodes_str and episodes_str.isdigit() else 0

        watched_str = el.findtext("my_watched_episodes", "0")
        my_watched = int(watched_str) if watched_str and watched_str.isdigit() else 0

        score_str = el.findtext("my_score", "0")
        my_score = int(score_str) if score_str and score_str.isdigit() else 0

        status = el.findtext("my_status") or "Plan to Watch"
        start_date = parse_mal_date(el.findtext("my_start_date"))
        finish_date = parse_mal_date(el.findtext("my_finish_date"))

        comments = el.findtext("my_comments") or ""
        tags = el.findtext("my_tags") or ""
        priority = (el.findtext("my_priority") or "LOW").upper()
        rewatching_str = el.findtext("my_rewatching", "0")
        my_rewatching = (rewatching_str == "1")

        # Progress calculation safe against 0 episodes
        progress_pct = calculate_progress_pct(my_watched, episodes)

        item: dict[str, Any] = {
            "id": mal_id,
            "title": title,
            "title_japanese": "",
            "synonyms": [],
            "type": series_type,
            "episodes": episodes,
            "my_watched_episodes": my_watched,
            "my_score": my_score,
            "my_status": status,
            "my_start_date": start_date,
            "my_finish_date": finish_date,
            "my_comments": comments,
            "my_tags": tags,
            "my_priority": priority,
            "my_rewatching": my_rewatching,
            "progress_pct": progress_pct,
            # Enriched metadata placeholders (populated by enricher)
            "poster_url": "",
            "genres": [],
            "studio": "",
            "synopsis": "",
            "global_score": None,
            "mal_url": f"https://myanimelist.net/anime/{mal_id}",
        }
        items.append(item)

    return items


def parse_manga_xml(source: Union[str, Path, bytes, BinaryIO, TextIO]) -> list[dict[str, Any]]:
    """
    Parse MAL manga XML export into normalized MangaItem dictionaries
    conforming to PROJECT.md § Interface Contracts.

    Total expected records: 47.
    """
    root = load_xml_root(source)
    items: list[dict[str, Any]] = []

    for el in root.findall("manga"):
        mal_id_str = el.findtext("manga_mangadb_id", "0")
        mal_id = int(mal_id_str) if mal_id_str and mal_id_str.isdigit() else 0

        title = el.findtext("manga_title") or ""
        manga_type = "Manga"

        chaps_str = el.findtext("manga_chapters", "0")
        chapters = int(chaps_str) if chaps_str and chaps_str.isdigit() else 0

        vols_str = el.findtext("manga_volumes", "0")
        volumes = int(vols_str) if vols_str and vols_str.isdigit() else 0

        read_chaps_str = el.findtext("my_read_chapters", "0")
        read_chapters = int(read_chaps_str) if read_chaps_str and read_chaps_str.isdigit() else 0

        read_vols_str = el.findtext("my_read_volumes", "0")
        read_volumes = int(read_vols_str) if read_vols_str and read_vols_str.isdigit() else 0

        score_str = el.findtext("my_score", "0")
        my_score = int(score_str) if score_str and score_str.isdigit() else 0

        status = el.findtext("my_status") or "Plan to Read"
        start_date = parse_mal_date(el.findtext("my_start_date"))
        finish_date = parse_mal_date(el.findtext("my_finish_date"))

        comments = el.findtext("my_comments") or ""
        tags = el.findtext("my_tags") or ""
        priority = (el.findtext("my_priority") or "Low").capitalize()
        rereading_str = (el.findtext("my_rereading") or "NO").strip().upper()
        my_rereading = (rereading_str == "YES")

        # Progress calculation safe against 0 chapters / 0 volumes
        chapter_pct = calculate_progress_pct(read_chapters, chapters)
        volume_pct = calculate_progress_pct(read_volumes, volumes)

        item: dict[str, Any] = {
            "id": mal_id,
            "title": title,
            "title_japanese": "",
            "synonyms": [],
            "type": manga_type,
            "chapters": chapters,
            "volumes": volumes,
            "my_read_chapters": read_chapters,
            "my_read_volumes": read_volumes,
            "my_score": my_score,
            "my_status": status,
            "my_start_date": start_date,
            "my_finish_date": finish_date,
            "my_comments": comments,
            "my_tags": tags,
            "my_priority": priority,
            "my_rereading": my_rereading,
            "chapter_progress_pct": chapter_pct,
            "volume_progress_pct": volume_pct,
            # Enriched metadata placeholders (populated by enricher)
            "poster_url": "",
            "genres": [],
            "authors": [],
            "synopsis": "",
            "global_score": None,
            "mal_url": f"https://myanimelist.net/manga/{mal_id}",
        }
        items.append(item)

    return items


def parse_catalog(
    anime_path: Union[str, Path] = "animelist_1788635141_-_7821911.xml.gz",
    manga_path: Union[str, Path] = "mangalist_1788635144_-_7821911.xml.gz",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """
    Parse both anime and manga MAL export archives and extract user metadata.

    Returns:
        (anime_items, manga_items, catalog_metadata)
    """
    anime_root = load_xml_root(anime_path)
    anime_items = parse_anime_xml(anime_root)
    manga_items = parse_manga_xml(manga_path)
    user_info = parse_user_info(anime_root)

    metadata = {
        "user_id": user_info.get("user_id"),
        "user_name": user_info.get("user_name", "hazza_bhaskara"),
        "export_date": "2026-09-05T19:05:41Z",
        "total_anime": len(anime_items),
        "total_manga": len(manga_items),
        "total_entries": len(anime_items) + len(manga_items),
    }

    return anime_items, manga_items, metadata


if __name__ == "__main__":
    print("Executing Parser Verification...")
    anime, manga, meta = parse_catalog()
    print(f"User: {meta['user_name']} (ID: {meta['user_id']})")
    print(f"Parsed Anime Count: {len(anime)} (Expected: 219)")
    print(f"Parsed Manga Count: {len(manga)} (Expected: 47)")
    print(f"Total Entries: {meta['total_entries']} (Expected: 266)")

    # Spot checks
    assert len(anime) == 219, f"Expected 219 anime, got {len(anime)}"
    assert len(manga) == 47, f"Expected 47 manga, got {len(manga)}"

    # Check non-ASCII title
    toubun = next(a for a in anime if "5-toubun" in a["title"] and "∬" in a["title"])
    print(f"Unicode title verified: {toubun['title']}")

    # Check partial date
    monster = next(a for a in anime if a["title"] == "Monster")
    print(f"Monster start date: {monster['my_start_date']} (Expected: '2021-03')")
    assert monster["my_start_date"] == "2021-03"

    # Check ongoing manga division by zero safe
    berserk = next(m for m in manga if m["title"] == "Berserk")
    print(f"Berserk chapters: {berserk['chapters']}, progress pct: {berserk['chapter_progress_pct']}%")
    assert berserk["chapters"] == 0
    assert berserk["chapter_progress_pct"] == 0.0

    print("All Parser Verification checks PASSED!")
