from __future__ import annotations

import httpx
import pytest

from worker.alliancetek.client import SupplierApiConfigError, SupplierApiError
from worker.alliancetek.errors import RETRY_DELAYS_SECONDS, SupplierErrorClass, classify_supplier_error


def _status_error(status_code: int) -> SupplierApiError:
    request = httpx.Request("POST", "https://sandbox.example.invalid/orders")
    response = httpx.Response(status_code, request=request)
    cause = httpx.HTTPStatusError(f"status {status_code}", request=request, response=response)
    err = SupplierApiError("simulated")
    err.__cause__ = cause
    return err


def _transport_error(cause_cls: type[Exception]) -> SupplierApiError:
    request = httpx.Request("GET", "https://sandbox.example.invalid/orders")
    cause = cause_cls("simulated transport failure", request=request)
    err = SupplierApiError("simulated")
    err.__cause__ = cause
    return err


def test_retry_delays_are_exact():
    assert RETRY_DELAYS_SECONDS == [0, 30, 120, 600, 1800]


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_transient_status_codes(status_code):
    assert classify_supplier_error(_status_error(status_code)) == SupplierErrorClass.TRANSIENT


def test_connect_timeout_is_transient():
    assert classify_supplier_error(_transport_error(httpx.ConnectTimeout)) == SupplierErrorClass.TRANSIENT


def test_read_timeout_is_transient():
    assert classify_supplier_error(_transport_error(httpx.ReadTimeout)) == SupplierErrorClass.TRANSIENT


def test_generic_network_failure_is_transient():
    assert classify_supplier_error(_transport_error(httpx.ConnectError)) == SupplierErrorClass.TRANSIENT


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
def test_permanent_status_codes(status_code):
    assert classify_supplier_error(_status_error(status_code)) == SupplierErrorClass.PERMANENT


def test_config_error_is_permanent():
    assert (
        classify_supplier_error(SupplierApiConfigError("SUPPLIER_API_ORDERS_URL is not configured."))
        == SupplierErrorClass.PERMANENT
    )


def test_unclassified_exception_defaults_to_permanent():
    """Never loop forever on something we don't understand — the safer
    default is to stop and flag for review, not retry indefinitely."""
    err = SupplierApiError("something unexpected")
    err.__cause__ = ValueError("not an httpx exception at all")
    assert classify_supplier_error(err) == SupplierErrorClass.PERMANENT
