from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker configuration, sourced from environment variables.

    Locally these come from `.env` via docker-compose. In deployed
    environments (ECS/Fargate) they are injected as task-definition
    environment variables, with secrets resolved from AWS Secrets Manager —
    never hardcoded here.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    log_level: str = "info"

    database_url: str = "postgresql+psycopg://timechain:changeme-local-only@db:5432/timechain"
    worker_poll_interval_seconds: int = 5

    # "local" (Postgres-backed background_jobs table) or "sqs". See
    # worker/queue/__init__.py's get_queue_provider — this is the only
    # place that switches between them.
    queue_provider: str = "local"

    # Go-live safety switches — see services/api/app/core/config.py's
    # checkout_enabled docstring for the same rationale. When false, the
    # corresponding job handler logs and returns without calling
    # AllianceTek or writing any supplier-facing rows; the job is still
    # deleted as a normal success (not left to retry forever).
    supplier_push_enabled: bool = True
    tracking_enabled: bool = True

    aws_region: str = "us-east-1"
    # Populated once queue_provider="sqs" is actually used in a deployed
    # environment; unused locally.
    sqs_queue_url: str = ""

    # AllianceTek Sandbox/Production API. Provided via environment
    # variables only — never hardcoded. Left blank by default so the
    # worker still boots without them; each caller (supplier_sync,
    # alliancetek.client) validates presence itself right before making a
    # request. Sandbox vs. production is entirely a matter of which
    # values are injected into this process — nothing in the client
    # itself branches on environment.
    supplier_api_products_url: str = ""
    supplier_api_orders_url: str = ""
    supplier_api_order_status_url: str = ""
    supplier_api_fulfillments_url: str = ""
    supplier_api_shipments_url: str = ""
    supplier_api_email: str = ""
    supplier_api_token: str = ""
    # Comma-separated supplier keys to sync in order (e.g. "umsrx,nxgen").
    # Each key selects a token below; the synced rows are stamped with the
    # key so the two disjoint pharmacy catalogs stay distinguishable.
    supplier_keys: str = "umsrx"
    supplier_umsrx_api_token: str = ""
    supplier_nxgen_api_token: str = ""
    supplier_api_timeout_seconds: float = 30.0
    supplier_api_max_retries: int = 3

    # Separate, parallel credential set used only by
    # worker.supplier_sync.production_report (python -m
    # worker.supplier_sync.production_report) — a read-only comparison of
    # the real AllianceTek production catalog against whatever is
    # currently in `supplier_products` (populated by the sandbox-pointed
    # supplier_api_* sync above). Deliberately distinct from
    # supplier_api_products_url/email/token: this tool needs both
    # environments' credentials live at once, unlike the normal sync,
    # which only ever points at one environment at a time.
    supplier_api_production_products_url: str = ""
    supplier_api_production_email: str = ""
    supplier_api_production_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
