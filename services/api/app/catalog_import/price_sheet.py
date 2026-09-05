from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Each sheet in the price sheet workbook has its own column layout, so
# headers are matched by candidate text (same "try known names, fail loudly
# if none match" style as worker/supplier_sync/mapping.py's _SKU_KEYS etc.)
# rather than by fixed column letters.
_PRODUCT_NAME_HEADERS = ("product", "product name")
_SIZE_HEADERS = ("pen size (mg)", "vial size (mg)", "size (mg)", "strength/concentration")
_WHOLESALE_HEADERS = ("wholesale price", "our selling price", "cost $")
_RETAIL_HEADERS = ("suggested retail", "new retail $")
_CATEGORY_HEADERS = ("category",)

# Analysis-only tabs in repricing workbooks (e.g. the v4 volume-ladder
# workbook's affiliate-margin / bulk-discount / summary sheets) carry
# product-looking rows but are not catalog sources — never parse them.
_SKIP_SHEET_MARKERS = ("affiliate", "bulk", "summary")

# Sheet name -> (form, default category used when the sheet has no explicit
# Category column). Form drives the form-match bonus in matching.py.
_SHEET_META: dict[str, tuple[str, str]] = {
    "RUO - PENS": ("pen", "RUO Pens"),
    "RUO - Vials": ("vial", "RUO Vials"),
    "RUO - Lyo": ("lyophilized", "RUO Lyophilized"),
    # Confirmed against the real "Vial and Pen Wholesale Pricing" workbook:
    # "RUO - FG Vials" is UMS's sheet name for their ready-to-use liquid
    # ("finished good") vials — the preconstituted format, as opposed to
    # NxGen Biomed's "RUO - Lyo" lyophilized-powder sheet.
    "RUO - FG Vials": ("preconstituted", "RUO Preconstituted"),
    "503a Houston Rx": ("rx_vial", "Prescription"),
}

_HEADER_SCAN_ROWS = 10
_MG_SIZE = re.compile(r"\s*mg\s*$", re.IGNORECASE)


class PriceSheetFormatError(RuntimeError):
    """Raised when a sheet's header row can't be located, or a required
    column (product name / wholesale / retail) isn't found under any known
    candidate name — better to stop than silently import wrong columns."""


@dataclass(frozen=True)
class PriceSheetRow:
    sheet: str
    form: str
    product_name: str
    size_key: Optional[str]
    category: Optional[str]
    wholesale_cents: Optional[int]
    retail_cents: Optional[int]


def _normalize_header(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _find_header_row(rows: list[tuple[Any, ...]], *, sheet_name: str) -> dict[str, int]:
    """Scans the first _HEADER_SCAN_ROWS rows for one containing a cell
    matching a product-name header candidate, and returns a map of
    normalized header text -> column index for that row."""
    for row in rows[:_HEADER_SCAN_ROWS]:
        headers = {_normalize_header(cell): col for col, cell in enumerate(row) if _normalize_header(cell)}
        if any(candidate in headers for candidate in _PRODUCT_NAME_HEADERS):
            return headers
    raise PriceSheetFormatError(
        f"Sheet {sheet_name!r}: no header row found in the first {_HEADER_SCAN_ROWS} rows "
        f"(checked for a cell matching {_PRODUCT_NAME_HEADERS})."
    )


def _first_column(headers: dict[str, int], candidates: tuple[str, ...]) -> Optional[int]:
    for candidate in candidates:
        if candidate in headers:
            return headers[candidate]
    return None


def parse_size_mg(value: Any) -> Optional[str]:
    """Normalizes a size/strength cell to a canonical mg string. Handles
    plain numbers (10.0 -> "10"), "50mg" -> "50", and combo doses like
    "10/10mg" -> "10/10". Returns None for blank/unparseable values."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    text = str(value).strip()
    if not text:
        return None
    text = _MG_SIZE.sub("", text)
    text = re.sub(r"\s*/\s*", "/", text.strip())
    return text or None


def _to_cents(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(round(value * 100))
    return None


def _sheet_meta(sheet_name: str) -> tuple[str, str]:
    if sheet_name in _SHEET_META:
        return _SHEET_META[sheet_name]
    lowered = sheet_name.lower()
    if "pen" in lowered:
        return "pen", sheet_name
    if "preconstitut" in lowered:
        return "preconstituted", sheet_name
    if "vial" in lowered:
        return "vial", sheet_name
    if "lyo" in lowered:
        return "lyophilized", sheet_name
    # Repricing workbooks name their catalog tab after the ladder itself
    # (e.g. "1 - VOLUME LADDER"); the ladder workbooks to date have priced
    # the lyophilized line, so a ladder tab is the lyo catalog sheet.
    if "ladder" in lowered or "volume" in lowered:
        return "lyophilized", "RUO Lyophilized"
    return "other", sheet_name


def parse_price_sheet(path: str | Path) -> list[PriceSheetRow]:
    """Parses every sheet of the TimeChain wholesale/retail price sheet
    workbook into a flat list of PriceSheetRow. Raises
    PriceSheetFormatError (rather than guessing) if a sheet is missing its
    product-name, wholesale, or retail column under any known name.
    """
    import openpyxl

    workbook = openpyxl.load_workbook(str(path), data_only=True)
    rows: list[PriceSheetRow] = []

    for sheet_name in workbook.sheetnames:
        if any(marker in sheet_name.lower() for marker in _SKIP_SHEET_MARKERS):
            continue
        worksheet = workbook[sheet_name]
        form, default_category = _sheet_meta(sheet_name)
        all_rows = list(worksheet.iter_rows(values_only=True))
        headers = _find_header_row(all_rows, sheet_name=sheet_name)

        name_col = _first_column(headers, _PRODUCT_NAME_HEADERS)
        wholesale_col = _first_column(headers, _WHOLESALE_HEADERS)
        retail_col = _first_column(headers, _RETAIL_HEADERS)
        # Retail is the customer-facing source of truth and the only
        # required price; wholesale/cost is optional (repricing workbooks
        # like the volume ladder carry retail only).
        if retail_col is None:
            raise PriceSheetFormatError(
                f"Sheet {sheet_name!r}: no retail-price column found "
                f"(checked {_RETAIL_HEADERS}). Headers seen: {sorted(headers)}"
            )
        size_col = _first_column(headers, _SIZE_HEADERS)
        category_col = _first_column(headers, _CATEGORY_HEADERS)

        header_row_index = next(
            i for i, row in enumerate(all_rows[:_HEADER_SCAN_ROWS])
            if any(_normalize_header(cell) in _PRODUCT_NAME_HEADERS for cell in row)
        )

        # Data is one contiguous block right after the header row in every
        # sheet observed so far — stop at the first row with no product
        # name rather than scanning to the sheet's padded max_row.
        for row in all_rows[header_row_index + 1 :]:
            product_name = row[name_col] if name_col < len(row) else None
            if product_name is None or not str(product_name).strip():
                break

            category = None
            if category_col is not None and category_col < len(row):
                category = row[category_col]
            rows.append(
                PriceSheetRow(
                    sheet=sheet_name,
                    form=form,
                    product_name=str(product_name).strip(),
                    size_key=parse_size_mg(row[size_col]) if size_col is not None and size_col < len(row) else None,
                    category=str(category).strip() if category else default_category,
                    wholesale_cents=_to_cents(row[wholesale_col])
                    if wholesale_col is not None and wholesale_col < len(row)
                    else None,
                    retail_cents=_to_cents(row[retail_col]) if retail_col < len(row) else None,
                )
            )

    return rows
