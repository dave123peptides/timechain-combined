"""Manual entrypoint: python -m worker.supplier_sync

Not wired into the worker's continuous loop yet — run it by hand (or from
a one-off ECS task / cron) until a sync schedule is decided.
"""

import logging
import sys

from worker.alliancetek.client import SupplierApiConfigError, SupplierApiError
from worker.supplier_sync.mapping import SupplierProductFieldError
from worker.supplier_sync.sync import SupplierSyncValidationError, run_sync

logging.basicConfig(level=logging.INFO)


def main() -> int:
    try:
        result = run_sync()
    except SupplierApiConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except (SupplierApiError, SupplierProductFieldError, SupplierSyncValidationError) as exc:
        print(f"Supplier sync failed: {exc}", file=sys.stderr)
        return 1

    print("Supplier sync summary:")
    print(f"  retrieved:           {result.retrieved}")
    print(f"  inserted:            {result.inserted}")
    print(f"  updated:             {result.updated}")
    print(f"  unchanged:           {result.unchanged}")
    print(f"  errors:              {result.errors}")
    print(f"  mappings_changed:    {result.mappings_changed}")
    print(f"  mappings_missing:    {result.mappings_missing}")
    print(f"  variants_deactivated: {result.variants_deactivated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
