from __future__ import annotations

from types import SimpleNamespace

from app.catalog_import.matching import classify_match
from app.catalog_import.price_sheet import parse_size_mg


def _supplier(supplier_product_id: int, sku: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(supplier_product_id=supplier_product_id, supplier_sku=sku, supplier_name=name)


def test_classify_match_exact_same_compound_same_dose_same_form():
    result = classify_match(
        product_name="BPC-157",
        size_key="20",
        form="vial",
        supplier_products=[_supplier(1, "S1", "BPC-157 10mL Vial 20mg (2mg/mL)")],
    )
    assert result.status == "EXACT"
    assert result.best is not None
    assert result.best.supplier_product_id == 1
    assert result.best.size_match is True


def test_classify_match_exact_same_compound_same_dose_preconstituted_form():
    """preconstituted must be recognized by both the noise-word stripper
    (so it doesn't hurt raw name similarity, same as "vial"/"lyophilized"
    today) and _FORM_HINTS (so a supplier name that says "Preconstituted"
    gets the same form-match bonus "vial" does)."""
    result = classify_match(
        product_name="BPC-157",
        size_key="20",
        form="preconstituted",
        supplier_products=[_supplier(1, "S1", "BPC-157 10mL Preconstituted 20mg (2mg/mL)")],
    )
    assert result.status == "EXACT"
    assert result.best is not None
    assert result.best.supplier_product_id == 1
    assert result.best.size_match is True


def test_classify_match_does_not_treat_a_combo_product_as_exact():
    """Regression guard: a short name like "Ipamorelin" must not be
    classified EXACT against a longer combo product name like "CJC (no
    DAC)/Ipamorelin" just because the short string is nearly a substring
    of the long one — a real false positive caught during development."""
    result = classify_match(
        product_name="Ipamorelin",
        size_key="10",
        form="pen",
        supplier_products=[_supplier(1, "S1", "CJC (no DAC)/Ipamorelin Size: 10mg")],
    )
    assert result.status != "EXACT"


def test_classify_match_likely_when_similar_but_not_confident():
    result = classify_match(
        product_name="Tesamorelin",
        size_key="30",
        form="vial",
        supplier_products=[_supplier(1, "S1", "Tesamorelin Complex 10mL Vial 45mg (mixed)")],
    )
    assert result.status == "LIKELY"
    assert result.best is not None
    assert result.best.size_match is False


def test_classify_match_ambiguous_when_two_candidates_tie():
    result = classify_match(
        product_name="Widget",
        size_key="10",
        form="vial",
        supplier_products=[
            _supplier(1, "S1", "Widget Formula A 10mL Vial 10mg"),
            _supplier(2, "S2", "Widget Formula B 10mL Vial 10mg"),
        ],
    )
    assert result.status == "AMBIGUOUS"
    assert len(result.candidates) == 2


def test_classify_match_no_match_when_dissimilar():
    result = classify_match(
        product_name="Totally Unrelated Compound",
        size_key="10",
        form="vial",
        supplier_products=[_supplier(1, "S1", "BPC-157 10mL Vial 20mg (2mg/mL)")],
    )
    assert result.status == "NO_MATCH"


def test_classify_match_no_match_when_no_supplier_products():
    result = classify_match(product_name="Widget", size_key="10", form="vial", supplier_products=[])
    assert result.status == "NO_MATCH"
    assert result.best is None
    assert result.candidates == []


def test_parse_size_mg_handles_numbers_strings_and_combos():
    assert parse_size_mg(10.0) == "10"
    assert parse_size_mg(7.5) == "7.5"
    assert parse_size_mg("50mg") == "50"
    assert parse_size_mg("10/10mg") == "10/10"
    assert parse_size_mg(None) is None
    assert parse_size_mg("") is None
