"""
Pipeline package for Animanga Showcase.
Provides data ingestion, XML parsing, and metadata enrichment engines.
"""

import sys

# Ensure UTF-8 stdout encoding on Windows systems to prevent UnicodeEncodeError
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

from .parser import (
    parse_anime_xml,
    parse_manga_xml,
    parse_mal_date,
    safe_div,
    calculate_progress_pct,
    parse_user_info,
    parse_catalog,
)

from .enricher import (
    enrich_catalog,
    enrich_items,
    load_cache,
    save_cache_atomic,
    MultiTierEnricher,
)

__all__ = [
    "parse_anime_xml",
    "parse_manga_xml",
    "parse_mal_date",
    "safe_div",
    "calculate_progress_pct",
    "parse_user_info",
    "parse_catalog",
    "enrich_catalog",
    "enrich_items",
    "load_cache",
    "save_cache_atomic",
    "MultiTierEnricher",
]
