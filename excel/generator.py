"""
Professional Excel Workbook Generator for Animanga Showcase.

Builds Animanga_Showcase.xlsx using openpyxl conforming to:
- Sheet 1: 'Anime List' (219 rows + 1 header row, A1:L220, freeze A2, conditional formatting)
- Sheet 2: 'Manga List' (47 rows + 1 header row, A1:N48, freeze A2, conditional formatting)
- Sheet 3: 'Overview & Stats' (Executive KPI Dashboard, formula cross-sheet references)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import openpyxl
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from pipeline.enricher import enrich_catalog
from pipeline.parser import parse_catalog

# Design System Color Constants
COLOR_SLATE_NAVY = "1E293B"
COLOR_SLATE_DARK = "334155"
COLOR_SLATE_TEXT = "0F172A"
COLOR_SLATE_MUTED = "475569"
COLOR_SLATE_LIGHT = "64748B"
COLOR_SLATE_BORDER = "E2E8F0"
COLOR_SLATE_CARD_BORDER = "CBD5E1"
COLOR_ZEBRA_ODD = "F8FAFC"
COLOR_ZEBRA_EVEN = "FFFFFF"
COLOR_CARD_LABEL_BG = "F1F5F9"
COLOR_INDIGO_PRIMARY = "4F46E5"
COLOR_TEAL_PRIMARY = "0D9488"
COLOR_AMBER_PRIMARY = "D97706"
COLOR_GREEN_PRIMARY = "16A34A"
COLOR_LINK_BLUE = "2563EB"

# Status Badges
COLOR_STATUS_COMPLETED_BG = "DCFCE7"
COLOR_STATUS_COMPLETED_TXT = "166534"
COLOR_STATUS_WATCHING_BG = "DBEAFE"
COLOR_STATUS_WATCHING_TXT = "1E40AF"
COLOR_STATUS_PLAN_BG = "F3E8FF"
COLOR_STATUS_PLAN_TXT = "6B21A8"
COLOR_STATUS_DROPPED_BG = "FEE2E2"
COLOR_STATUS_DROPPED_TXT = "991B1B"
COLOR_STATUS_ONHOLD_BG = "FEF08A"
COLOR_STATUS_ONHOLD_TXT = "854D0E"

# Score Heatmap
COLOR_SCORE_MIN = "FCA5A5"   # 1
COLOR_SCORE_MID = "FDE047"   # 6
COLOR_SCORE_MAX = "86EFAC"   # 10


def _create_borders():
    """Create reusable border styles."""
    thin = Side(style="thin", color=COLOR_SLATE_BORDER)
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)

    header_side = Side(style="thin", color="334155")
    header_bottom = Side(style="medium", color="0F172A")
    header_border = Border(left=header_side, right=header_side, top=header_side, bottom=header_bottom)

    card_side = Side(style="thin", color=COLOR_SLATE_CARD_BORDER)
    card_border = Border(left=card_side, right=card_side, top=card_side, bottom=card_side)

    summary_border = Border(
        top=Side(style="thin", color="94A3B8"),
        bottom=Side(style="double", color=COLOR_SLATE_NAVY),
        left=thin,
        right=thin,
    )

    return thin_border, header_border, card_border, summary_border


def _style_range(
    ws,
    min_col: int,
    min_row: int,
    max_col: int,
    max_row: int,
    font: Optional[Font] = None,
    fill: Optional[PatternFill] = None,
    border: Optional[Border] = None,
    alignment: Optional[Alignment] = None,
):
    """Apply styling to a 2D range of cells (useful for merged ranges)."""
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            cell = ws.cell(row=r, column=c)
            if font is not None:
                cell.font = font
            if fill is not None:
                cell.fill = fill
            if border is not None:
                cell.border = border
            if alignment is not None:
                cell.alignment = alignment


def _auto_fit_columns(ws, max_col: int, padding: int = 4, min_width: int = 12, max_width: int = 55):
    """Auto-adjust column widths based on maximum content length with safety padding."""
    for col_idx in range(1, max_col + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for cell in ws[col_letter]:
            val = cell.value
            if val is not None:
                # Handle formula representation
                val_str = str(val)
                if val_str.startswith("="):
                    # Guess sensible display length for formulas
                    if "HYPERLINK" in val_str:
                        val_str = "View on MAL"
                    elif "AVERAGEIF" in val_str or "COUNTIF" in val_str:
                        val_str = "100.0%"
                    elif "COUNTA" in val_str or "SUM" in val_str:
                        val_str = "999,999"
                    else:
                        val_str = "100.0%"
                # Newlines count maximum line length
                lines = val_str.split("\n")
                line_len = max(len(l) for l in lines) if lines else 0
                if line_len > max_len:
                    max_len = line_len

        adjusted_width = max(min_width, min(max_len + padding, max_width))
        ws.column_dimensions[col_letter].width = adjusted_width


def _apply_conditional_formatting(ws, score_col_letter: str, status_col_letter: str, start_row: int, end_row: int):
    """Apply score heatmap and status badge rules to list worksheets."""
    # 1. Score 3-Color Scale (1 to 10)
    score_range = f"{score_col_letter}{start_row}:{score_col_letter}{end_row}"
    color_scale = ColorScaleRule(
        start_type="num",
        start_value=1,
        start_color=COLOR_SCORE_MIN,
        mid_type="num",
        mid_value=6,
        mid_color=COLOR_SCORE_MID,
        end_type="num",
        end_value=10,
        end_color=COLOR_SCORE_MAX,
    )
    ws.conditional_formatting.add(score_range, color_scale)

    # 2. Status Badges
    status_range = f"{status_col_letter}{start_row}:{status_col_letter}{end_row}"
    status_rules = [
        CellIsRule(
            operator="equal",
            formula=['"Completed"'],
            fill=PatternFill(start_color=COLOR_STATUS_COMPLETED_BG, end_color=COLOR_STATUS_COMPLETED_BG, fill_type="solid"),
            font=Font(name="Calibri", size=10, bold=True, color=COLOR_STATUS_COMPLETED_TXT),
        ),
        CellIsRule(
            operator="equal",
            formula=['"Watching"'],
            fill=PatternFill(start_color=COLOR_STATUS_WATCHING_BG, end_color=COLOR_STATUS_WATCHING_BG, fill_type="solid"),
            font=Font(name="Calibri", size=10, bold=True, color=COLOR_STATUS_WATCHING_TXT),
        ),
        CellIsRule(
            operator="equal",
            formula=['"Reading"'],
            fill=PatternFill(start_color=COLOR_STATUS_WATCHING_BG, end_color=COLOR_STATUS_WATCHING_BG, fill_type="solid"),
            font=Font(name="Calibri", size=10, bold=True, color=COLOR_STATUS_WATCHING_TXT),
        ),
        CellIsRule(
            operator="equal",
            formula=['"Plan to Watch"'],
            fill=PatternFill(start_color=COLOR_STATUS_PLAN_BG, end_color=COLOR_STATUS_PLAN_BG, fill_type="solid"),
            font=Font(name="Calibri", size=10, bold=True, color=COLOR_STATUS_PLAN_TXT),
        ),
        CellIsRule(
            operator="equal",
            formula=['"Plan to Read"'],
            fill=PatternFill(start_color=COLOR_STATUS_PLAN_BG, end_color=COLOR_STATUS_PLAN_BG, fill_type="solid"),
            font=Font(name="Calibri", size=10, bold=True, color=COLOR_STATUS_PLAN_TXT),
        ),
        CellIsRule(
            operator="equal",
            formula=['"Dropped"'],
            fill=PatternFill(start_color=COLOR_STATUS_DROPPED_BG, end_color=COLOR_STATUS_DROPPED_BG, fill_type="solid"),
            font=Font(name="Calibri", size=10, bold=True, color=COLOR_STATUS_DROPPED_TXT),
        ),
        CellIsRule(
            operator="equal",
            formula=['"On-Hold"'],
            fill=PatternFill(start_color=COLOR_STATUS_ONHOLD_BG, end_color=COLOR_STATUS_ONHOLD_BG, fill_type="solid"),
            font=Font(name="Calibri", size=10, bold=True, color=COLOR_STATUS_ONHOLD_TXT),
        ),
    ]

    for rule in status_rules:
        ws.conditional_formatting.add(status_range, rule)


def _build_anime_sheet(wb: openpyxl.Workbook, anime_items: list[dict[str, Any]]) -> openpyxl.worksheet.worksheet.Worksheet:
    """Build Sheet 1: 'Anime List'."""
    ws = wb.create_sheet(title="Anime List")
    ws.views.sheetView[0].showGridLines = True

    thin_border, header_border, _, _ = _create_borders()

    headers = [
        "MAL ID",
        "Title",
        "Format",
        "Episodes",
        "Watched",
        "Progress %",
        "My Score",
        "Status",
        "Genres",
        "Studio",
        "Global Score",
        "MAL URL",
    ]

    # Row 1: Header
    ws.row_dimensions[1].height = 28
    header_fill = PatternFill(start_color=COLOR_SLATE_NAVY, end_color=COLOR_SLATE_NAVY, fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, text in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=text)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = header_border
        cell.alignment = header_alignment

    # Data Rows
    data_font = Font(name="Calibri", size=10, color=COLOR_SLATE_TEXT)
    link_font = Font(name="Calibri", size=10, color=COLOR_LINK_BLUE, underline="single")

    fill_even = PatternFill(start_color=COLOR_ZEBRA_EVEN, end_color=COLOR_ZEBRA_EVEN, fill_type="solid")
    fill_odd = PatternFill(start_color=COLOR_ZEBRA_ODD, end_color=COLOR_ZEBRA_ODD, fill_type="solid")

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    for idx, item in enumerate(anime_items, start=2):
        ws.row_dimensions[idx].height = 20
        row_fill = fill_even if idx % 2 == 0 else fill_odd

        mal_id = item.get("id", 0)
        title = item.get("title", "")
        format_type = item.get("type", "TV")
        episodes = item.get("episodes", 0)
        watched = item.get("my_watched_episodes", 0)
        progress_formula = f'=IF(D{idx}>0, E{idx}/D{idx}, IF(H{idx}="Completed", 1, 0))'
        my_score = item.get("my_score", 0)
        status = item.get("my_status", "Plan to Watch")
        genres = ", ".join(item.get("genres", [])) if isinstance(item.get("genres"), list) else ""
        studio = item.get("studio", "")
        global_score = item.get("global_score")
        mal_url = item.get("mal_url") or f"https://myanimelist.net/anime/{mal_id}"

        # Col A: MAL ID
        c_a = ws.cell(row=idx, column=1, value=mal_id)
        c_a.alignment = align_center
        c_a.number_format = "0"

        # Col B: Title
        c_b = ws.cell(row=idx, column=2, value=title)
        c_b.alignment = align_left

        # Col C: Format
        c_c = ws.cell(row=idx, column=3, value=format_type)
        c_c.alignment = align_center

        # Col D: Episodes
        c_d = ws.cell(row=idx, column=4, value=episodes)
        c_d.alignment = align_right
        c_d.number_format = "#,##0"

        # Col E: Watched
        c_e = ws.cell(row=idx, column=5, value=watched)
        c_e.alignment = align_right
        c_e.number_format = "#,##0"

        # Col F: Progress %
        c_f = ws.cell(row=idx, column=6, value=progress_formula)
        c_f.alignment = align_right
        c_f.number_format = "0.0%"

        # Col G: My Score
        c_g = ws.cell(row=idx, column=7, value=my_score)
        c_g.alignment = align_center
        c_g.number_format = "0"

        # Col H: Status
        c_h = ws.cell(row=idx, column=8, value=status)
        c_h.alignment = align_center

        # Col I: Genres
        c_i = ws.cell(row=idx, column=9, value=genres)
        c_i.alignment = align_left

        # Col J: Studio
        c_j = ws.cell(row=idx, column=10, value=studio)
        c_j.alignment = align_left

        # Col K: Global Score
        c_k = ws.cell(row=idx, column=11, value=float(global_score) if global_score is not None else "")
        c_k.alignment = align_center
        if global_score is not None:
            c_k.number_format = "0.00"

        # Col L: MAL URL
        c_l = ws.cell(row=idx, column=12, value=mal_url)
        c_l.alignment = align_left
        c_l.hyperlink = mal_url
        c_l.font = link_font

        # Apply fonts, borders, fills
        for col_idx in range(1, 13):
            cell = ws.cell(row=idx, column=col_idx)
            cell.border = thin_border
            cell.fill = row_fill
            if col_idx != 12:
                cell.font = data_font

    total_rows = len(anime_items) + 1
    # Frozen header pane at row 2 (A2)
    ws.freeze_panes = "A2"
    # Auto-filters enabled on A1:L220
    ws.auto_filter.ref = f"A1:L{total_rows}"

    # Conditional Formatting: scores on col G (G2:G220), status on col H (H2:H220)
    _apply_conditional_formatting(ws, score_col_letter="G", status_col_letter="H", start_row=2, end_row=total_rows)

    # Auto-fit column widths
    _auto_fit_columns(ws, max_col=12, padding=4, min_width=12, max_width=50)

    return ws


def _build_manga_sheet(wb: openpyxl.Workbook, manga_items: list[dict[str, Any]]) -> openpyxl.worksheet.worksheet.Worksheet:
    """Build Sheet 2: 'Manga List'."""
    ws = wb.create_sheet(title="Manga List")
    ws.views.sheetView[0].showGridLines = True

    thin_border, header_border, _, _ = _create_borders()

    headers = [
        "MAL ID",
        "Title",
        "Type",
        "Chapters",
        "Volumes",
        "Read Chapters",
        "Read Volumes",
        "Progress %",
        "My Score",
        "Status",
        "Genres",
        "Authors",
        "Global Score",
        "MAL URL",
    ]

    # Row 1: Header
    ws.row_dimensions[1].height = 28
    header_fill = PatternFill(start_color=COLOR_SLATE_NAVY, end_color=COLOR_SLATE_NAVY, fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, text in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=text)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = header_border
        cell.alignment = header_alignment

    # Data Rows
    data_font = Font(name="Calibri", size=10, color=COLOR_SLATE_TEXT)
    link_font = Font(name="Calibri", size=10, color=COLOR_LINK_BLUE, underline="single")

    fill_even = PatternFill(start_color=COLOR_ZEBRA_EVEN, end_color=COLOR_ZEBRA_EVEN, fill_type="solid")
    fill_odd = PatternFill(start_color=COLOR_ZEBRA_ODD, end_color=COLOR_ZEBRA_ODD, fill_type="solid")

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    for idx, item in enumerate(manga_items, start=2):
        ws.row_dimensions[idx].height = 20
        row_fill = fill_even if idx % 2 == 0 else fill_odd

        mal_id = item.get("id", 0)
        title = item.get("title", "")
        manga_type = item.get("type", "Manga")
        chapters = item.get("chapters", 0)
        volumes = item.get("volumes", 0)
        read_chapters = item.get("my_read_chapters", 0)
        read_volumes = item.get("my_read_volumes", 0)
        progress_formula = f'=IF(D{idx}>0, F{idx}/D{idx}, IF(J{idx}="Completed", 1, 0))'
        my_score = item.get("my_score", 0)
        status = item.get("my_status", "Plan to Read")
        genres = ", ".join(item.get("genres", [])) if isinstance(item.get("genres"), list) else ""
        authors = ", ".join(item.get("authors", [])) if isinstance(item.get("authors"), list) else item.get("authors", "")
        global_score = item.get("global_score")
        mal_url = item.get("mal_url") or f"https://myanimelist.net/manga/{mal_id}"

        # Col A: MAL ID
        c_a = ws.cell(row=idx, column=1, value=mal_id)
        c_a.alignment = align_center
        c_a.number_format = "0"

        # Col B: Title
        c_b = ws.cell(row=idx, column=2, value=title)
        c_b.alignment = align_left

        # Col C: Type
        c_c = ws.cell(row=idx, column=3, value=manga_type)
        c_c.alignment = align_center

        # Col D: Chapters
        c_d = ws.cell(row=idx, column=4, value=chapters)
        c_d.alignment = align_right
        c_d.number_format = "#,##0"

        # Col E: Volumes
        c_e = ws.cell(row=idx, column=5, value=volumes)
        c_e.alignment = align_right
        c_e.number_format = "#,##0"

        # Col F: Read Chapters
        c_f = ws.cell(row=idx, column=6, value=read_chapters)
        c_f.alignment = align_right
        c_f.number_format = "#,##0"

        # Col G: Read Volumes
        c_g = ws.cell(row=idx, column=7, value=read_volumes)
        c_g.alignment = align_right
        c_g.number_format = "#,##0"

        # Col H: Progress %
        c_h = ws.cell(row=idx, column=8, value=progress_formula)
        c_h.alignment = align_right
        c_h.number_format = "0.0%"

        # Col I: My Score
        c_i = ws.cell(row=idx, column=9, value=my_score)
        c_i.alignment = align_center
        c_i.number_format = "0"

        # Col J: Status
        c_j = ws.cell(row=idx, column=10, value=status)
        c_j.alignment = align_center

        # Col K: Genres
        c_k = ws.cell(row=idx, column=11, value=genres)
        c_k.alignment = align_left

        # Col L: Authors
        c_l = ws.cell(row=idx, column=12, value=authors)
        c_l.alignment = align_left

        # Col M: Global Score
        c_m = ws.cell(row=idx, column=13, value=float(global_score) if global_score is not None else "")
        c_m.alignment = align_center
        if global_score is not None:
            c_m.number_format = "0.00"

        # Col N: MAL URL
        c_n = ws.cell(row=idx, column=14, value=mal_url)
        c_n.alignment = align_left
        c_n.hyperlink = mal_url
        c_n.font = link_font

        # Apply fonts, borders, fills
        for col_idx in range(1, 15):
            cell = ws.cell(row=idx, column=col_idx)
            cell.border = thin_border
            cell.fill = row_fill
            if col_idx != 14:
                cell.font = data_font

    total_rows = len(manga_items) + 1
    # Frozen header pane at row 2 (A2)
    ws.freeze_panes = "A2"
    # Auto-filters enabled on A1:N48
    ws.auto_filter.ref = f"A1:N{total_rows}"

    # Conditional Formatting: scores on col I (I2:I48), status on col J (J2:J48)
    _apply_conditional_formatting(ws, score_col_letter="I", status_col_letter="J", start_row=2, end_row=total_rows)

    # Auto-fit column widths
    _auto_fit_columns(ws, max_col=14, padding=4, min_width=12, max_width=50)

    return ws


def _build_overview_sheet(
    wb: openpyxl.Workbook,
    anime_items: list[dict[str, Any]],
    manga_items: list[dict[str, Any]],
) -> openpyxl.worksheet.worksheet.Worksheet:
    """Build Sheet 3: 'Overview & Stats' (Executive Analytics Dashboard)."""
    ws = wb.create_sheet(title="Overview & Stats")
    ws.views.sheetView[0].showGridLines = True

    thin_border, header_border, card_border, summary_border = _create_borders()

    # Column Widths Setup for Dashboard Layout
    col_widths = {
        "A": 3,
        "B": 24,
        "C": 16,
        "D": 16,
        "E": 16,
        "F": 22,
        "G": 4,
        "H": 22,
        "I": 16,
        "J": 16,
        "K": 16,
        "L": 22,
    }
    for col_l, width in col_widths.items():
        ws.column_dimensions[col_l].width = width

    # Row 1: Margin spacing
    ws.row_dimensions[1].height = 10

    # Row 2: Title Banner
    ws.row_dimensions[2].height = 36
    _style_range(
        ws,
        min_col=2,
        min_row=2,
        max_col=12,
        max_row=2,
        font=Font(name="Calibri", size=15, bold=True, color="FFFFFF"),
        fill=PatternFill(start_color=COLOR_SLATE_NAVY, end_color=COLOR_SLATE_NAVY, fill_type="solid"),
        border=header_border,
        alignment=Alignment(horizontal="center", vertical="center"),
    )
    ws.merge_cells("B2:L2")
    ws["B2"] = "ANIMANGA SHOWCASE — EXECUTIVE ANALYTICS DASHBOARD"

    # Row 3: Subtitle Banner
    ws.row_dimensions[3].height = 20
    _style_range(
        ws,
        min_col=2,
        min_row=3,
        max_col=12,
        max_row=3,
        font=Font(name="Calibri", size=9.5, italic=True, color="CBD5E1"),
        fill=PatternFill(start_color=COLOR_SLATE_DARK, end_color=COLOR_SLATE_DARK, fill_type="solid"),
        border=Border(bottom=Side(style="medium", color="0F172A")),
        alignment=Alignment(horizontal="center", vertical="center"),
    )
    ws.merge_cells("B3:L3")
    ws["B3"] = "Real-time Metrics & Insights for 219 Anime & 47 Manga • Powered by MyAnimeList Export Data"

    # Row 4: Spacer
    ws.row_dimensions[4].height = 12

    # Row 5: Section Header 1
    ws.row_dimensions[5].height = 22
    ws["B5"] = "EXECUTIVE SUMMARY KPIS"
    ws["B5"].font = Font(name="Calibri", size=11, bold=True, color=COLOR_SLATE_NAVY)

    # Reusable Helper for KPI Cards
    def create_kpi_card(
        col_start: int,
        col_end: int,
        row_lbl: int,
        row_val_start: int,
        row_val_end: int,
        label: str,
        formula: str,
        num_format: str,
        val_color: str = COLOR_SLATE_NAVY,
    ):
        lbl_col_start_l = get_column_letter(col_start)
        lbl_col_end_l = get_column_letter(col_end)

        # Style Label Area
        _style_range(
            ws,
            min_col=col_start,
            min_row=row_lbl,
            max_col=col_end,
            max_row=row_lbl,
            font=Font(name="Calibri", size=9, bold=True, color=COLOR_SLATE_MUTED),
            fill=PatternFill(start_color=COLOR_CARD_LABEL_BG, end_color=COLOR_CARD_LABEL_BG, fill_type="solid"),
            border=card_border,
            alignment=Alignment(horizontal="center", vertical="center"),
        )
        ws.merge_cells(f"{lbl_col_start_l}{row_lbl}:{lbl_col_end_l}{row_lbl}")
        ws[f"{lbl_col_start_l}{row_lbl}"] = label

        # Style Value Area
        _style_range(
            ws,
            min_col=col_start,
            min_row=row_val_start,
            max_col=col_end,
            max_row=row_val_end,
            font=Font(name="Calibri", size=20, bold=True, color=val_color),
            fill=PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid"),
            border=card_border,
            alignment=Alignment(horizontal="center", vertical="center"),
        )
        ws.merge_cells(f"{lbl_col_start_l}{row_val_start}:{lbl_col_end_l}{row_val_end}")
        val_cell = ws[f"{lbl_col_start_l}{row_val_start}"]
        val_cell.value = formula
        val_cell.number_format = num_format

    # Row Dimensions for KPI Cards
    ws.row_dimensions[6].height = 18
    ws.row_dimensions[7].height = 20
    ws.row_dimensions[8].height = 20
    ws.row_dimensions[9].height = 8

    ws.row_dimensions[10].height = 18
    ws.row_dimensions[11].height = 20
    ws.row_dimensions[12].height = 20
    ws.row_dimensions[13].height = 8

    ws.row_dimensions[14].height = 18
    ws.row_dimensions[15].height = 20
    ws.row_dimensions[16].height = 20

    # KPI Row 1:
    # Card 1: Total Titles: =COUNTA('Anime List'!B2:B220) + COUNTA('Manga List'!B2:B48)
    create_kpi_card(
        col_start=2,
        col_end=4,
        row_lbl=6,
        row_val_start=7,
        row_val_end=8,
        label="TOTAL TITLES",
        formula="=COUNTA('Anime List'!B2:B220) + COUNTA('Manga List'!B2:B48)",
        num_format="#,##0",
        val_color=COLOR_SLATE_NAVY,
    )
    # Card 2: Total Anime: =COUNTA('Anime List'!B2:B220)
    create_kpi_card(
        col_start=5,
        col_end=7,
        row_lbl=6,
        row_val_start=7,
        row_val_end=8,
        label="TOTAL ANIME",
        formula="=COUNTA('Anime List'!B2:B220)",
        num_format="#,##0",
        val_color=COLOR_INDIGO_PRIMARY,
    )
    # Card 3: Total Manga: =COUNTA('Manga List'!B2:B48)
    create_kpi_card(
        col_start=8,
        col_end=10,
        row_lbl=6,
        row_val_start=7,
        row_val_end=8,
        label="TOTAL MANGA",
        formula="=COUNTA('Manga List'!B2:B48)",
        num_format="#,##0",
        val_color=COLOR_TEAL_PRIMARY,
    )

    # KPI Row 2:
    # Card 4: Total Episodes Watched: =SUM('Anime List'!E2:E220)
    create_kpi_card(
        col_start=2,
        col_end=4,
        row_lbl=10,
        row_val_start=11,
        row_val_end=12,
        label="TOTAL EPISODES WATCHED",
        formula="=SUM('Anime List'!E2:E220)",
        num_format="#,##0",
        val_color=COLOR_SLATE_NAVY,
    )
    # Card 5: Total Chapters Read: =SUM('Manga List'!F2:F48)
    create_kpi_card(
        col_start=5,
        col_end=7,
        row_lbl=10,
        row_val_start=11,
        row_val_end=12,
        label="TOTAL CHAPTERS READ",
        formula="=SUM('Manga List'!F2:F48)",
        num_format="#,##0",
        val_color=COLOR_SLATE_NAVY,
    )
    # Card 6: Anime Mean Score: =AVERAGEIF('Anime List'!G2:G220, ">0")
    create_kpi_card(
        col_start=8,
        col_end=10,
        row_lbl=10,
        row_val_start=11,
        row_val_end=12,
        label="ANIME MEAN SCORE (RATED)",
        formula='=AVERAGEIF(\'Anime List\'!G2:G220, ">0")',
        num_format="0.00",
        val_color=COLOR_AMBER_PRIMARY,
    )

    # KPI Row 3:
    # Card 7: Manga Mean Score: =AVERAGEIF('Manga List'!I2:I48, ">0")
    create_kpi_card(
        col_start=2,
        col_end=4,
        row_lbl=14,
        row_val_start=15,
        row_val_end=16,
        label="MANGA MEAN SCORE (RATED)",
        formula='=AVERAGEIF(\'Manga List\'!I2:I48, ">0")',
        num_format="0.00",
        val_color=COLOR_AMBER_PRIMARY,
    )
    # Card 8: Anime Completion Rate: =COUNTIF('Anime List'!H2:H220, "Completed") / COUNTA('Anime List'!B2:B220)
    create_kpi_card(
        col_start=5,
        col_end=7,
        row_lbl=14,
        row_val_start=15,
        row_val_end=16,
        label="ANIME COMPLETION RATE",
        formula='=COUNTIF(\'Anime List\'!H2:H220, "Completed") / COUNTA(\'Anime List\'!B2:B220)',
        num_format="0.0%",
        val_color=COLOR_GREEN_PRIMARY,
    )
    # Card 9: Manga Completion Rate: =COUNTIF('Manga List'!J2:J48, "Completed") / COUNTA('Manga List'!B2:B48)
    create_kpi_card(
        col_start=8,
        col_end=10,
        row_lbl=14,
        row_val_start=15,
        row_val_end=16,
        label="MANGA COMPLETION RATE",
        formula='=COUNTIF(\'Manga List\'!J2:J48, "Completed") / COUNTA(\'Manga List\'!B2:B48)',
        num_format="0.0%",
        val_color=COLOR_GREEN_PRIMARY,
    )

    # Row 17: Spacer
    ws.row_dimensions[17].height = 14

    # Row 18: Section Header 2
    ws.row_dimensions[18].height = 22
    ws["B18"] = "STATUS BREAKDOWN"
    ws["B18"].font = Font(name="Calibri", size=11, bold=True, color=COLOR_SLATE_NAVY)
    ws["H18"] = "SCORE DISTRIBUTION"
    ws["H18"].font = Font(name="Calibri", size=11, bold=True, color=COLOR_SLATE_NAVY)

    # Table Headers: Status Breakdown (B19:F19) & Score Distribution (H19:K19)
    ws.row_dimensions[19].height = 24
    tbl_hdr_fill = PatternFill(start_color=COLOR_SLATE_DARK, end_color=COLOR_SLATE_DARK, fill_type="solid")
    tbl_hdr_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")

    # Status Breakdown Headers
    status_headers = [("B", "Status"), ("C", "Anime"), ("D", "Manga"), ("E", "Total"), ("F", "% Share")]
    for col_l, text in status_headers:
        c = ws[f"{col_l}19"]
        c.value = text
        c.fill = tbl_hdr_fill
        c.font = tbl_hdr_font
        c.border = header_border
        c.alignment = Alignment(horizontal="center", vertical="center")

    # Score Distribution Headers
    score_headers = [("H", "Score Tier"), ("I", "Anime"), ("J", "Manga"), ("K", "Total"), ("L", "% Share")]
    for col_l, text in score_headers:
        c = ws[f"{col_l}19"]
        c.value = text
        c.fill = tbl_hdr_fill
        c.font = tbl_hdr_font
        c.border = header_border
        c.alignment = Alignment(horizontal="center", vertical="center")

    # Status Breakdown Rows (Rows 20-24)
    data_font = Font(name="Calibri", size=10, color=COLOR_SLATE_TEXT)
    data_font_bold = Font(name="Calibri", size=10, bold=True, color=COLOR_SLATE_TEXT)
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    fill_even = PatternFill(start_color=COLOR_ZEBRA_EVEN, end_color=COLOR_ZEBRA_EVEN, fill_type="solid")
    fill_odd = PatternFill(start_color=COLOR_ZEBRA_ODD, end_color=COLOR_ZEBRA_ODD, fill_type="solid")

    status_data = [
        ("Completed", "Completed", "Completed"),
        ("Watching / Reading", "Watching", "Reading"),
        ("Plan to Watch / Read", "Plan to Watch", "Plan to Read"),
        ("On-Hold", "On-Hold", "On-Hold"),
        ("Dropped", "Dropped", "Dropped"),
    ]

    for idx, (label, anime_status, manga_status) in enumerate(status_data, start=20):
        ws.row_dimensions[idx].height = 20
        row_fill = fill_even if idx % 2 == 0 else fill_odd

        # Col B: Status Label
        b = ws[f"B{idx}"]
        b.value = label
        b.font = data_font
        b.fill = row_fill
        b.border = thin_border
        b.alignment = align_left

        # Col C: Anime Count
        c = ws[f"C{idx}"]
        c.value = f'=COUNTIF(\'Anime List\'!H2:H220, "{anime_status}")'
        c.font = data_font
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_right
        c.number_format = "#,##0"

        # Col D: Manga Count
        d = ws[f"D{idx}"]
        d.value = f'=COUNTIF(\'Manga List\'!J2:J48, "{manga_status}")'
        d.font = data_font
        d.fill = row_fill
        d.border = thin_border
        d.alignment = align_right
        d.number_format = "#,##0"

        # Col E: Total
        e = ws[f"E{idx}"]
        e.value = f"=C{idx}+D{idx}"
        e.font = data_font_bold
        e.fill = row_fill
        e.border = thin_border
        e.alignment = align_right
        e.number_format = "#,##0"

        # Col F: % Share
        f = ws[f"F{idx}"]
        f.value = f"=E{idx}/$E$25"
        f.font = data_font
        f.fill = row_fill
        f.border = thin_border
        f.alignment = align_right
        f.number_format = "0.0%"

    # Status Summary Row (Row 25)
    ws.row_dimensions[25].height = 22
    summary_fill = PatternFill(start_color=COLOR_CARD_LABEL_BG, end_color=COLOR_CARD_LABEL_BG, fill_type="solid")

    ws["B25"].value = "Total"
    ws["B25"].font = data_font_bold
    ws["B25"].fill = summary_fill
    ws["B25"].border = summary_border
    ws["B25"].alignment = align_left

    ws["C25"].value = "=SUM(C20:C24)"
    ws["C25"].font = data_font_bold
    ws["C25"].fill = summary_fill
    ws["C25"].border = summary_border
    ws["C25"].alignment = align_right
    ws["C25"].number_format = "#,##0"

    ws["D25"].value = "=SUM(D20:D24)"
    ws["D25"].font = data_font_bold
    ws["D25"].fill = summary_fill
    ws["D25"].border = summary_border
    ws["D25"].alignment = align_right
    ws["D25"].number_format = "#,##0"

    ws["E25"].value = "=SUM(E20:E24)"
    ws["E25"].font = data_font_bold
    ws["E25"].fill = summary_fill
    ws["E25"].border = summary_border
    ws["E25"].alignment = align_right
    ws["E25"].number_format = "#,##0"

    ws["F25"].value = "=SUM(F20:F24)"
    ws["F25"].font = data_font_bold
    ws["F25"].fill = summary_fill
    ws["F25"].border = summary_border
    ws["F25"].alignment = align_right
    ws["F25"].number_format = "0.0%"

    # Score Distribution Rows (Rows 20-25)
    score_data = [
        ("★ 10 Masterpiece", "=COUNTIF('Anime List'!G2:G220, 10)", "=COUNTIF('Manga List'!I2:I48, 10)"),
        ("★ 9 Great", "=COUNTIF('Anime List'!G2:G220, 9)", "=COUNTIF('Manga List'!I2:I48, 9)"),
        ("★ 7-8 Good", "=COUNTIF('Anime List'!G2:G220, 7) + COUNTIF('Anime List'!G2:G220, 8)", "=COUNTIF('Manga List'!I2:I48, 7) + COUNTIF('Manga List'!I2:I48, 8)"),
        ("★ 5-6 Average", "=COUNTIF('Anime List'!G2:G220, 5) + COUNTIF('Anime List'!G2:G220, 6)", "=COUNTIF('Manga List'!I2:I48, 5) + COUNTIF('Manga List'!I2:I48, 6)"),
        ("★ 1-4 Low", "=COUNTIF('Anime List'!G2:G220, \">=1\") - COUNTIF('Anime List'!G2:G220, \">=5\")", "=COUNTIF('Manga List'!I2:I48, \">=1\") - COUNTIF('Manga List'!I2:I48, \">=5\")"),
        ("Unrated (0)", "=COUNTIF('Anime List'!G2:G220, 0)", "=COUNTIF('Manga List'!I2:I48, 0)"),
    ]

    for idx, (tier_label, anime_f, manga_f) in enumerate(score_data, start=20):
        row_fill = fill_even if idx % 2 == 0 else fill_odd

        # Col H: Score Tier
        h = ws[f"H{idx}"]
        h.value = tier_label
        h.font = data_font
        h.fill = row_fill
        h.border = thin_border
        h.alignment = align_left

        # Col I: Anime
        i = ws[f"I{idx}"]
        i.value = anime_f
        i.font = data_font
        i.fill = row_fill
        i.border = thin_border
        i.alignment = align_right
        i.number_format = "#,##0"

        # Col J: Manga
        j = ws[f"J{idx}"]
        j.value = manga_f
        j.font = data_font
        j.fill = row_fill
        j.border = thin_border
        j.alignment = align_right
        j.number_format = "#,##0"

        # Col K: Total
        k = ws[f"K{idx}"]
        k.value = f"=I{idx}+J{idx}"
        k.font = data_font_bold
        k.fill = row_fill
        k.border = thin_border
        k.alignment = align_right
        k.number_format = "#,##0"

        # Col L: % Share
        l = ws[f"L{idx}"]
        l.value = f"=K{idx}/$K$26"
        l.font = data_font
        l.fill = row_fill
        l.border = thin_border
        l.alignment = align_right
        l.number_format = "0.0%"

    # Score Distribution Summary Row (Row 26)
    ws.row_dimensions[26].height = 22
    ws["H26"].value = "Total Titles"
    ws["H26"].font = data_font_bold
    ws["H26"].fill = summary_fill
    ws["H26"].border = summary_border
    ws["H26"].alignment = align_left

    ws["I26"].value = "=SUM(I20:I25)"
    ws["I26"].font = data_font_bold
    ws["I26"].fill = summary_fill
    ws["I26"].border = summary_border
    ws["I26"].alignment = align_right
    ws["I26"].number_format = "#,##0"

    ws["J26"].value = "=SUM(J20:J25)"
    ws["J26"].font = data_font_bold
    ws["J26"].fill = summary_fill
    ws["J26"].border = summary_border
    ws["J26"].alignment = align_right
    ws["J26"].number_format = "#,##0"

    ws["K26"].value = "=SUM(K20:K25)"
    ws["K26"].font = data_font_bold
    ws["K26"].fill = summary_fill
    ws["K26"].border = summary_border
    ws["K26"].alignment = align_right
    ws["K26"].number_format = "#,##0"

    ws["L26"].value = "=SUM(L20:L25)"
    ws["L26"].font = data_font_bold
    ws["L26"].fill = summary_fill
    ws["L26"].border = summary_border
    ws["L26"].alignment = align_right
    ws["L26"].number_format = "0.0%"

    # Row 27: Spacer
    ws.row_dimensions[27].height = 14

    # Row 28: Section Header 3
    ws.row_dimensions[28].height = 22
    ws["B28"] = "TOP 10 RATED ANIME"
    ws["B28"].font = Font(name="Calibri", size=11, bold=True, color=COLOR_SLATE_NAVY)
    ws["H28"] = "TOP 10 RATED MANGA"
    ws["H28"].font = Font(name="Calibri", size=11, bold=True, color=COLOR_SLATE_NAVY)

    # Row 29: Top Rated Headers
    ws.row_dimensions[29].height = 24
    top_anime_headers = [("B", "Rank"), ("C", "Title"), ("D", "Score"), ("E", "Global"), ("F", "Studio")]
    for col_l, text in top_anime_headers:
        c = ws[f"{col_l}29"]
        c.value = text
        c.fill = tbl_hdr_fill
        c.font = tbl_hdr_font
        c.border = header_border
        c.alignment = align_center

    top_manga_headers = [("H", "Rank"), ("I", "Title"), ("J", "Score"), ("K", "Global"), ("L", "Author")]
    for col_l, text in top_manga_headers:
        c = ws[f"{col_l}29"]
        c.value = text
        c.fill = tbl_hdr_fill
        c.font = tbl_hdr_font
        c.border = header_border
        c.alignment = align_center

    # Sort Anime and Manga by Score descending, then Global Score descending
    sorted_anime = sorted(
        anime_items,
        key=lambda x: (x.get("my_score", 0), x.get("global_score") or 0.0),
        reverse=True,
    )[:10]

    sorted_manga = sorted(
        manga_items,
        key=lambda x: (x.get("my_score", 0), x.get("global_score") or 0.0),
        reverse=True,
    )[:10]

    for rank, (a_item, m_item) in enumerate(zip(sorted_anime, sorted_manga), start=1):
        row_idx = 29 + rank
        ws.row_dimensions[row_idx].height = 20
        row_fill = fill_even if rank % 2 == 0 else fill_odd

        # Anime Top 10
        # Col B: Rank
        c = ws[f"B{row_idx}"]
        c.value = rank
        c.font = data_font_bold
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_center

        # Col C: Title
        c = ws[f"C{row_idx}"]
        c.value = a_item.get("title", "")
        c.font = data_font
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_left

        # Col D: Score
        c = ws[f"D{row_idx}"]
        c.value = a_item.get("my_score", 0)
        c.font = data_font_bold
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_center
        c.number_format = "0"

        # Col E: Global Score
        c = ws[f"E{row_idx}"]
        g_sc = a_item.get("global_score")
        c.value = float(g_sc) if g_sc is not None else ""
        c.font = data_font
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_center
        if g_sc is not None:
            c.number_format = "0.00"

        # Col F: Studio
        c = ws[f"F{row_idx}"]
        c.value = a_item.get("studio", "")
        c.font = data_font
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_left

        # Manga Top 10
        # Col H: Rank
        c = ws[f"H{row_idx}"]
        c.value = rank
        c.font = data_font_bold
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_center

        # Col I: Title
        c = ws[f"I{row_idx}"]
        c.value = m_item.get("title", "")
        c.font = data_font
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_left

        # Col J: Score
        c = ws[f"J{row_idx}"]
        c.value = m_item.get("my_score", 0)
        c.font = data_font_bold
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_center
        c.number_format = "0"

        # Col K: Global Score
        c = ws[f"K{row_idx}"]
        g_sc_m = m_item.get("global_score")
        c.value = float(g_sc_m) if g_sc_m is not None else ""
        c.font = data_font
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_center
        if g_sc_m is not None:
            c.number_format = "0.00"

        # Col L: Author
        c = ws[f"L{row_idx}"]
        auth_list = m_item.get("authors", [])
        c.value = ", ".join(auth_list) if isinstance(auth_list, list) else str(auth_list)
        c.font = data_font
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_left

    # Row 40: Spacer
    ws.row_dimensions[40].height = 14

    # Row 41: Section Header 4: Genre Distribution Breakdown
    ws.row_dimensions[41].height = 22
    ws["B41"] = "GENRE DISTRIBUTION BREAKDOWN (TOP 10 GENRES)"
    ws["B41"].font = Font(name="Calibri", size=11, bold=True, color=COLOR_SLATE_NAVY)

    # Row 42: Genre Distribution Headers (Cols B:F)
    ws.row_dimensions[42].height = 24
    genre_headers = [("B", "Genre Name"), ("C", "Anime Count"), ("D", "Manga Count"), ("E", "Total Frequency"), ("F", "% of Catalog")]
    for col_l, text in genre_headers:
        c = ws[f"{col_l}42"]
        c.value = text
        c.fill = tbl_hdr_fill
        c.font = tbl_hdr_font
        c.border = header_border
        c.alignment = align_center

    top_genres = [
        "Drama",
        "Comedy",
        "Slice of Life",
        "Romance",
        "Supernatural",
        "Action",
        "Fantasy",
        "Psychological",
        "Adventure",
        "Mystery",
    ]

    for idx, genre in enumerate(top_genres, start=43):
        ws.row_dimensions[idx].height = 20
        row_fill = fill_even if idx % 2 == 0 else fill_odd

        # Col B: Genre Name
        b = ws[f"B{idx}"]
        b.value = genre
        b.font = data_font_bold
        b.fill = row_fill
        b.border = thin_border
        b.alignment = align_left

        # Col C: Anime Count
        c = ws[f"C{idx}"]
        c.value = f'=COUNTIF(\'Anime List\'!I$2:I$220, "*{genre}*")'
        c.font = data_font
        c.fill = row_fill
        c.border = thin_border
        c.alignment = align_right
        c.number_format = "#,##0"

        # Col D: Manga Count
        d = ws[f"D{idx}"]
        d.value = f'=COUNTIF(\'Manga List\'!K$2:K$48, "*{genre}*")'
        d.font = data_font
        d.fill = row_fill
        d.border = thin_border
        d.alignment = align_right
        d.number_format = "#,##0"

        # Col E: Total Frequency
        e = ws[f"E{idx}"]
        e.value = f"=C{idx}+D{idx}"
        e.font = data_font_bold
        e.fill = row_fill
        e.border = thin_border
        e.alignment = align_right
        e.number_format = "#,##0"

        # Col F: % of Catalog (referencing Total Titles from KPI Card 1 cell B7)
        f = ws[f"F{idx}"]
        f.value = f"=E{idx}/(COUNTA('Anime List'!B$2:B$220) + COUNTA('Manga List'!B$2:B$48))"
        f.font = data_font
        f.fill = row_fill
        f.border = thin_border
        f.alignment = align_right
        f.number_format = "0.0%"

    return ws


def generate_excel_workbook(
    output_path: str | Path = "Animanga_Showcase.xlsx",
    anime_items: Optional[list[dict[str, Any]]] = None,
    manga_items: Optional[list[dict[str, Any]]] = None,
) -> str:
    """
    Generate the complete, professionally styled Excel Workbook.

    Creates three worksheets:
    1. 'Anime List': 219 anime records with auto-filters, frozen panes, zebra striping, conditional formatting.
    2. 'Manga List': 47 manga records with auto-filters, frozen panes, zebra striping, conditional formatting.
    3. 'Overview & Stats': Executive KPI dashboard with dynamic formula cross-references.
    """
    output_file = Path(output_path)

    # 1. Obtain data if not passed directly
    if anime_items is None or manga_items is None:
        parsed_anime, parsed_manga, _ = parse_catalog()
        anime_items, manga_items = enrich_catalog(parsed_anime, parsed_manga, offline=True)

    # 2. Create openpyxl Workbook
    wb = openpyxl.Workbook()
    # Remove default sheet to maintain clean exact sheet ordering
    default_sheet = wb.active

    # 3. Build Worksheets in strict order
    _build_anime_sheet(wb, anime_items)
    _build_manga_sheet(wb, manga_items)
    _build_overview_sheet(wb, anime_items, manga_items)

    # Remove the placeholder sheet
    if default_sheet is not None and default_sheet in wb.worksheets:
        wb.remove(default_sheet)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 4. Save workbook
    wb.save(output_file)
    print(f"[Excel] Successfully generated workbook: {output_file.resolve()} (Sheets: {wb.sheetnames})")

    return str(output_file.resolve())


if __name__ == "__main__":
    generate_excel_workbook()
