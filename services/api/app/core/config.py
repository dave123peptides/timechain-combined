from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _site_origins(site_url: str) -> list[str]:
    """`https://www.example.com/` -> both `https://www.example.com` and
    `https://example.com` (and vice versa). Empty or unparsable -> []."""
    parts = urlsplit(site_url.strip())
    if not parts.scheme or not parts.netloc:
        return []
    host = parts.netloc.lower()
    twin = host[4:] if host.startswith("www.") else f"www.{host}"
    return [f"{parts.scheme}://{host}", f"{parts.scheme}://{twin}"]


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables.

    Locally these come from `.env` via docker-compose. In deployed
    environments (ECS/Fargate) they are injected as task-definition
    environment variables, with secrets resolved from AWS Secrets Manager —
    never hardcoded here.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    log_level: str = "info"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"

    database_url: str = "postgresql+psycopg://timechain:changeme-local-only@db:5432/timechain"

    @field_validator("database_url", mode="before")
    @classmethod
    def _force_psycopg3_driver(cls, value):
        # SQLAlchemy maps a bare postgresql:// scheme to the psycopg2
        # driver, which is not a dependency (psycopg3 is). Normalize any
        # incoming URL so the driver is always explicit.
        if isinstance(value, str):
            if value.startswith("postgres://"):
                value = "postgresql://" + value[len("postgres://"):]
            if value.startswith("postgresql://"):
                value = "postgresql+psycopg://" + value[len("postgresql://"):]
        return value

    # Go-live safety switch. False makes the storefront present as empty
    # and checkout as unavailable, without touching any data — used to
    # run production catalog/mapping work (e.g. a production supplier
    # sync) ahead of actually opening the storefront to real customers.
    checkout_enabled: bool = True

    # Blank by default — admin_auth.py fails closed (401) whenever either
    # is blank, so an unconfigured deployment locks admin out rather than
    # silently leaving it open.
    admin_basic_auth_user: str = ""
    admin_basic_auth_password: str = ""

    # How a PAID order reaches the supplier (David, 9/4):
    #   "manual"       — the default. Nothing is pushed anywhere; David
    #                    places the order with the supplier himself from
    #                    the admin orders page / CSV export / the new-order
    #                    webhook. mark_order_paid records an
    #                    awaiting_manual_fulfillment event instead of
    #                    enqueueing submit_supplier_order.
    #   "supplier_api" — the original flow: mark_order_paid enqueues
    #                    submit_supplier_order for the worker.
    fulfillment_mode: str = "manual"

    # Optional. When set, every newly placed order is POSTed here as JSON
    # (app/services/order_notify.py) — point it at a Zapier / Make
    # "catch hook" that appends a row to a Google Sheet, or anything else
    # that accepts JSON. Best-effort and fire-and-forget: a failure is
    # logged and never affects the customer's checkout.
    order_notify_webhook_url: str = ""

    # GoHighLevel CRM push (app/services/ghl_notify.py). When set, every
    # newly placed order is POSTed (customer-safe fields only) to a GHL
    # workflow's Inbound Webhook URL, which creates/updates the contact
    # and emails the customer their order number + payment steps.
    # This is the pens site's OWN workflow (distinct from the vial
    # storefront's) so PEN- orders are told apart in the CRM.
    # Blank = feature off.
    ghl_order_webhook_url: str = ""

    # Google Sheets order feed (docs/plans/google-sheets-order-feed.md).
    # Every new order is appended as a row to the named tab via a service
    # account. Blank spreadsheet id = feature off.
    google_sheets_orders_spreadsheet_id: str = ""
    google_sheets_orders_tab: str = "Orders"
    # Full JSON key contents (one line). Preferred over a file path because
    # hosted platforms inject env vars, not files.
    google_service_account_json: str = ""
    # Alternative auth for Google Workspaces that block service-account
    # keys via org policy: a one-line JSON with refresh_token/client_id/
    # client_secret/token_uri (spreadsheets scope). Used only when the
    # service-account key is blank.
    google_sheets_refresh_token_json: str = ""

    # --- Speed (Bitcoin payments — see app/payments/speed.py) ---
    # Blank key = crypto checkout degrades gracefully (order created, no
    # payment instructions) rather than erroring — see SpeedProvider.
    # Keys come from the Speed merchant dashboard (app.tryspeed.com →
    # Developers → API Keys); sk_test_ / sk_live_ prefixes.
    speed_api_key: str = ""
    speed_api_base: str = "https://api.tryspeed.com"
    # 2022-10-15 = on-chain + Lightning + ETH/SOL/TRON; 2022-04-15 would
    # be Lightning-only. We always offer the customer the full choice.
    speed_api_version: str = "2022-10-15"
    # Endpoint secret from Dashboard → Developers → Webhooks (wsec_...).
    # Used to verify webhook signatures; blank until the endpoint exists
    # (needs a public URL — the Vercel deployment).
    speed_webhook_secret: str = ""
    # Public base URL of the storefront. Builds the checkout session's
    # success_url (where the payer lands after paying). Blank locally is
    # fine: Speed just can't redirect back until a public URL exists.
    public_site_url: str = ""
    # Optional https URL to a logo shown on Speed's hosted payment page.
    public_site_logo_url: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [origin.strip().rstrip("/") for origin in self.api_cors_origins.split(",") if origin.strip()]
        # The storefront's own origin is always allowed, in both its bare
        # and www forms: the cart drawer, checkout and admin page call the
        # API from the browser, and a missing CORS entry is exactly what
        # took the live cart down on 2026-09-05 ("No longer available" on
        # every line because /shop/products was blocked).
        for origin in _site_origins(self.public_site_url):
            if origin not in origins:
                origins.append(origin)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
