from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Literal, Optional, Protocol, Sequence

MatchStatus = Literal["EXACT", "LIKELY", "AMBIGUOUS", "NO_MATCH"]

# Deliberately conservative: only a high-confidence, unambiguous top match
# is EXACT. Anything close-scoring or merely similar is left for a human —
# see the "Matching is conservative on purpose" note in the plan. Tune
# these after reviewing real output, not by guessing.
# EXACT requires BOTH a high blended score AND a high raw name-similarity
# ratio. The blended score alone isn't safe as the sole gate: a short name
# like "Ipamorelin" can score deceptively high against a longer combo
# product's name like "CJC (no DAC)/Ipamorelin" purely because the short
# string is nearly a substring of the long one — a real false positive
# caught by hand-checking real supplier data during development. Requiring
# a high *raw* name ratio (before size/form bonuses) closes that gap.
EXACT_MIN_SCORE = 0.97
EXACT_MIN_NAME_RATIO = 0.90
EXACT_MIN_GAP = 0.03
LIKELY_MIN_SCORE = 0.6
AMBIGUOUS_MAX_GAP = 0.05

_CandidateLimit = 5

_PAREN = re.compile(r"\([^)]*\)")
# "Month N" is a TimeChain-specific dose-tier label (Pens sheet) — the dose
# itself is already captured separately via size_key, so it's noise for
# *name* comparison, not part of the product's identity.
_MONTH_TIER = re.compile(r"\bmonth\s*\d+\b", re.IGNORECASE)
# Both sides tend to embed the dose in the name too (e.g. supplier_name
# "Tirzepatide 10mg Pen Size: 10mg") — strip standalone number/mg tokens so
# name comparison judges product identity, not dose, which is scored
# separately via size_match.
_NUMERIC_TOKEN = re.compile(r"\b\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?){0,3}\s*(?:mg)?\b", re.IGNORECASE)
# Fill volume (e.g. "3mL", "10mL Vial") is packaging detail, not product
# identity — strip it too, same reasoning as _NUMERIC_TOKEN above.
_VOLUME_TOKEN = re.compile(r"\b\d+(?:\.\d+)?\s*mL\b", re.IGNORECASE)
_NOISE_WORDS = re.compile(
    r"\b(vial|vials|pen|pens|cartridge|cartridges|size|lyophilized|lyo|preconstituted|reconstituted|premixed)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SIZE_TOKEN = re.compile(r"(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?){0,3})\s*mg\b", re.IGNORECASE)

# Lyophilized vials live in the NxGen pharmacy catalog; UMSRx carries pens
# and pre-constituted vials. The supplier catalogs do not reliably encode
# "lyophilized" in the product NAME (a UMSRx "BPC-157 10mg" pen and an
# NxGen "BPC-157 - 10mg" powder score identically), so for lyo price-sheet
# rows the supplier key is the only dependable form signal. Rows without a
# supplier_key attribute (test doubles) are kept, so unit tests control
# their own candidate pools.
_LYO_SUPPLIER_KEY = "nxgen"

# Sheet `form` -> substrings that, if found in a supplier_name, suggest the
# same physical form. Advisory only (a score bonus, never a requirement) —
# supplier names don't reliably encode form (e.g. "AOD-9604 Size: 5mg" has
# no form keyword at all).
_FORM_HINTS: dict[str, tuple[str, ...]] = {
    "pen": ("pen", "cartridge"),
    "vial": ("vial",),
    "rx_vial": ("vial",),
    "lyophilized": (),
    "preconstituted": ("preconstituted", "reconstituted", "premixed", "ready to use", "ready-to-use", "liquid"),
    "other": (),
}


class SupplierProductLike(Protocol):
    """Structural type — matches the real SupplierProduct ORM model and
    lightweight test doubles alike. This module never touches the
    database; it's a pure scoring function."""

    supplier_product_id: int
    supplier_sku: str
    supplier_name: str


@dataclass(frozen=True)
class MatchCandidate:
    supplier_product_id: int
    supplier_sku: str
    supplier_name: str
    score: float
    name_ratio: float
    size_match: bool


@dataclass(frozen=True)
class MatchResult:
    status: MatchStatus
    best: Optional[MatchCandidate]
    candidates: list[MatchCandidate]


def _normalize_name(text: str) -> str:
    text = _PAREN.sub(" ", text)
    text = _MONTH_TIER.sub(" ", text)
    text = _VOLUME_TOKEN.sub(" ", text)
    text = _NUMERIC_TOKEN.sub(" ", text)
    text = _NOISE_WORDS.sub(" ", text)
    text = _NON_ALNUM.sub(" ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _normalize_size(size_key: Optional[str]) -> Optional[str]:
    if not size_key:
        return None
    return re.sub(r"\s*/\s*", "/", size_key.strip()) or None


def _extract_size(text: str) -> Optional[str]:
    match = _SIZE_TOKEN.search(text)
    if not match:
        return None
    return re.sub(r"\s*/\s*", "/", match.group(1))


def classify_match(
    *,
    product_name: str,
    size_key: Optional[str],
    form: str,
    supplier_products: Sequence[SupplierProductLike],
) -> MatchResult:
    """Scores `product_name`/`size_key` (from a TimeChain price-sheet row)
    against every active-or-inactive supplier product and classifies the
    best match. Pure function — no DB access, so it's cheap to unit test
    with plain objects instead of real SupplierProduct rows.
    """
    if not supplier_products:
        return MatchResult(status="NO_MATCH", best=None, candidates=[])

    if form == "lyophilized":
        # Lyo rows may only match the NxGen catalog — see _LYO_SUPPLIER_KEY.
        # Without this, a "BPC-157 10mg" lyo row scores identically against
        # the pen, the liquid vial, and the lyo powder and the tie is a
        # coin flip.
        supplier_products = [
            sp
            for sp in supplier_products
            if getattr(sp, "supplier_key", _LYO_SUPPLIER_KEY) == _LYO_SUPPLIER_KEY
        ]
        if not supplier_products:
            return MatchResult(status="NO_MATCH", best=None, candidates=[])

    norm_target_name = _normalize_name(product_name)
    norm_target_size = _normalize_size(size_key)
    form_hints = _FORM_HINTS.get(form, ())

    scored: list[MatchCandidate] = []
    for supplier_product in supplier_products:
        norm_supplier_name = _normalize_name(supplier_product.supplier_name)
        name_score = difflib.SequenceMatcher(None, norm_target_name, norm_supplier_name).ratio()

        supplier_size = _extract_size(supplier_product.supplier_name)
        size_match = norm_target_size is not None and supplier_size is not None and norm_target_size == supplier_size

        form_match = bool(form_hints) and any(
            hint in supplier_product.supplier_name.lower() for hint in form_hints
        )

        score = name_score + (0.15 if size_match else 0.0) + (0.05 if form_match else 0.0)
        scored.append(
            MatchCandidate(
                supplier_product_id=supplier_product.supplier_product_id,
                supplier_sku=supplier_product.supplier_sku,
                supplier_name=supplier_product.supplier_name,
                score=round(score, 6),
                name_ratio=round(name_score, 6),
                size_match=size_match,
            )
        )

    scored.sort(key=lambda candidate: candidate.score, reverse=True)
    top_candidates = scored[:_CandidateLimit]

    best = scored[0]
    runner_up_score = scored[1].score if len(scored) > 1 else 0.0
    gap = best.score - runner_up_score

    if (
        best.score >= EXACT_MIN_SCORE
        and best.name_ratio >= EXACT_MIN_NAME_RATIO
        and best.size_match
        and gap >= EXACT_MIN_GAP
    ):
        return MatchResult(status="EXACT", best=best, candidates=top_candidates)

    if best.score >= LIKELY_MIN_SCORE and gap < AMBIGUOUS_MAX_GAP and len(scored) > 1:
        return MatchResult(status="AMBIGUOUS", best=best, candidates=top_candidates)

    if best.score >= LIKELY_MIN_SCORE:
        return MatchResult(status="LIKELY", best=best, candidates=top_candidates)

    return MatchResult(status="NO_MATCH", best=best, candidates=top_candidates)
