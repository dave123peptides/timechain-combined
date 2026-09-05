import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, object_session, relationship, validates
from sqlalchemy.sql import func

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Our customer-facing catalog entry — merchandising information only.
    Never used when talking to a supplier; see `SupplierProduct` for that."""

    __tablename__ = "products"

    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    # Ordered list of image URLs, e.g. ["https://.../front.jpg", "https://.../label.jpg"].
    images: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # Structured PDP copy: {overview, key_points: [...], research_areas:
    # [...], pairs_with: [slug, ...], faq: [{q, a}, ...]}. All optional —
    # the frontend only renders sections that are present. See
    # app.scripts.sync_product_content for the authored content and
    # app.services.storefront for the response shape.
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    # Safety Data Sheet PDF, surfaced as a PDP link and on /coa. NULL is a
    # meaningful state, not missing data — no SDS exists for this catalog
    # yet, and the frontend renders an honest "available on request"
    # instead. Never substitute a claim for a document.
    #
    # Certificates of Analysis do NOT live here: a product accumulates one
    # certificate per lot per strength (hundreds across the catalog), so
    # they are rows in `ProductCoa` below. A single `coa_url` column used
    # to sit alongside sds_url; it was dropped when the certificates
    # arrived, so there is exactly one source of truth for them.
    sds_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    coas: Mapped[list["ProductCoa"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductCoa(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One third-party Certificate of Analysis: one lab report for one
    lot of one strength of a product. Surfaced per strength in the PDP's
    Lab report tab and on /coa, each opening the lab's own hosted PDF
    with its verification code.

    Rows are loaded from data/coa/coa_manifest.csv by
    app.scripts.sync_coas; the manifest is built from the certificate
    PDFs themselves by app.scripts.build_coa_manifest. Nothing here is
    typed in by hand — every field traces back to a certificate the
    customer can verify with the lab via `verify_url`.

    Never store a purity figure here. The certificate carries the number
    in its own context (method, specification, chromatogram); a purity
    percentage pulled out of it and shown on its own is exactly the
    headline-number claim the storefront's copy commits not to make (see
    ProofSection / the about page).
    """

    __tablename__ = "product_coas"
    __table_args__ = (Index("ix_product_coas_product_strength_issued", "product_id", "strength", "issued_on"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The lab's verification code, printed on the certificate and used
    # by its Accuverify page — the natural key for a certificate.
    verify_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    # Same shape as ProductVariant.size_key ("10", "10/10/50", "10mL") so
    # the Lab report cards line up with the strength picker. Nullable in
    # principle only — the manifest builder always sets it.
    strength: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lot: Mapped[str] = mapped_column(Text, nullable=False)
    # The certificate's published date — when the lab certified the
    # results, not when the sample was received.
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    lab: Mapped[str] = mapped_column(Text, nullable=False)
    # Who the lab issued the certificate to (our supplier). Kept so an
    # admin can see, and sync_coas can gate on, whose paperwork this is.
    client: Mapped[str] = mapped_column(Text, nullable=False)
    # Assay labels as they appear on the certificate, e.g.
    # ["Identity", "Purity (HPLC)", "Quantity", "Endotoxin (LAL)",
    # "Sterility (PCR)"]. Shown so a customer knows what the report
    # covers before opening it; never a result, only the panel.
    tests: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    pdf_url: Mapped[str] = mapped_column(Text, nullable=False)
    verify_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Original filename in the COA folder, for reconciling against the
    # supplier's exports. Internal only.
    source_file: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # The storefront only ever reads published rows. sync_coas sets this
    # on insert (by client — see its docstring) and never flips it on a
    # re-run, so a deliberate manual hide/show survives every sync.
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    product: Mapped["Product"] = relationship(back_populates="coas")


class ProductVariant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A purchasable SKU of a product (e.g. a specific size/strength).
    Retail price and wholesale cost live here, not on `SupplierProduct` —
    they're our merchandising numbers, independent of which supplier (or
    how many) currently fulfill this variant."""

    __tablename__ = "product_variants"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Integer cents — never float — for every money column in this schema.
    retail_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    wholesale_cost_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd", server_default="usd")
    # Normalized dose (e.g. "20", "10/10") and physical form (pen/vial/
    # lyophilized/preconstituted/rx_vial/other — see
    # app.constants.forms.FORM_LABEL for the full recognized set and
    # display labels) from the price-sheet row this variant was created
    # from. Nullable — only populated by catalog_import; existing rows
    # created before this column existed backfill on the next
    # `python -m app.catalog_import.run`. Exists so the admin page can
    # feed classify_match() a live confidence check without needing to
    # reverse-parse them out of `name`/`sku`.
    size_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    form: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Defaults to False, not True: a variant must have a verified supplier
    # mapping before it can be sellable — see _validate_is_sellable below.
    # A bare `default=True` here would let any code path that omits
    # is_sellable in the constructor bypass that validator entirely, since
    # column defaults are applied at flush time, not through the
    # instrumented attribute setter that @validates hooks into.
    is_sellable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    product: Mapped["Product"] = relationship(back_populates="variants")
    supplier_mappings: Mapped[list["SupplierProductMapping"]] = relationship(
        back_populates="product_variant", cascade="all, delete-orphan"
    )
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product_variant")

    @validates("is_sellable")
    def _validate_is_sellable(self, key: str, value: bool) -> bool:
        """Application-level enforcement: is_sellable may only become True
        when this variant has a verified (MAPPED) supplier mapping. Every
        other mapping_status — MISSING, CHANGED, or never-mapped
        LIKELY/AMBIGUOUS/UNMAPPED rows from catalog import — blocks it.
        Fires on every assignment through the ORM (constructor kwargs
        included), which is the only way this app ever writes the column.

        Pens are categorically excluded from this business (David's
        explicit, repeated direction) — blocked here unconditionally,
        before the mapping-status check, so this can never regress via a
        future catalog import or an admin mis-click. This is not a
        temporary sourcing gap like MISSING/CHANGED; it's a permanent
        product-line decision.
        """
        if not value:
            return value

        if self.form != "lyophilized":
            raise ValueError(
                f"Cannot set is_sellable=True on variant {self.sku!r}: only lyophilized vials are sold on this site."
            )

        session = object_session(self)
        if session is None:
            raise ValueError(
                "Cannot set is_sellable=True before this ProductVariant is attached to a session — "
                "its supplier mapping status can't be verified yet."
            )

        # Local import: app.services.mapping_status imports this module for
        # SupplierProduct/SupplierProductMapping, so a top-level import here
        # would be circular.
        from app.services.mapping_status import get_mapping_status

        status = get_mapping_status(session, self.id)
        if status != "MAPPED":
            raise ValueError(
                f"Cannot set is_sellable=True on variant {self.sku!r}: supplier mapping status is "
                f"{status!r}, not MAPPED."
            )
        return value


class SupplierProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A product exactly as it exists in the supplier's (ShipStation)
    catalog. This is raw supplier truth, not merchandising data — nothing
    here is customer-facing, and nothing customer-facing (`Product.name`,
    slug, etc.) belongs here.

    `supplier_product_id` is the supplier's permanent numeric identifier
    and is stable, so it's safe to use as a foreign key target.
    `supplier_sku` / `supplier_name` are not — the supplier can rename or
    re-SKU a product on a later sync — so mappings snapshot them instead
    of relying on a live join. See `SupplierProductMapping`.
    """

    __tablename__ = "supplier_products"
    __table_args__ = (
        Index(
            "ix_supplier_products_active_true",
            "supplier_active",
            postgresql_where=text("supplier_active = true"),
        ),
        Index("ix_supplier_products_last_seen_at", "last_seen_at"),
    )

    # The supplier's own product id. Stable over time — safe as an FK target.
    supplier_product_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    # Which pharmacy account this product came from. The middleware serves
    # two disjoint catalogs behind two tokens ("umsrx" = pens &
    # pre-constituted, "nxgen" = lyophilized vials), and product ids are
    # only unique WITHIN a supplier — so every lookup/join that cares
    # which supplier a product belongs to must filter on this too.
    # Defaults to "umsrx" because that is the legacy single-token sync's
    # supplier; the dual-sync migration backfills the rest.
    supplier_key: Mapped[str] = mapped_column(String(20), nullable=False, server_default="umsrx", default="umsrx")
    # TEXT, not a bounded/typed SKU column — some supplier SKUs mix letters
    # and hyphens (e.g. "5AM1-50"), so this must never be coerced to a number.
    supplier_sku: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    # The exact product name as given by the supplier — required verbatim
    # in ShipStation order payloads. Distinct from `Product.name`.
    supplier_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    supplier_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supplier_price_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Full raw payload from the supplier feed/API, kept for audit and to
    # avoid re-fetching if we need a field we didn't originally model.
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # When we first saw this supplier product, and the last time a catalog
    # sync confirmed it still exists — distinct from created_at/updated_at,
    # which just track this row's own lifecycle.
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    mappings: Mapped[list["SupplierProductMapping"]] = relationship(
        back_populates="supplier_product", cascade="all, delete-orphan"
    )


class SupplierProductMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Links a sellable variant to the supplier product that fulfills it.

    `supplier_product_id` is a live foreign key (the supplier's id is
    stable). `supplier_sku` and `supplier_name` are frozen copies taken
    from `SupplierProduct` when the mapping was made/last verified — order
    submission must read them from here, never from a live join to
    `SupplierProduct` (which a catalog re-sync could have changed since)
    and never from `Product.name` (the customer-facing title, which the
    supplier doesn't know and won't match in ShipStation).
    """

    __tablename__ = "supplier_product_mappings"
    __table_args__ = (
        UniqueConstraint(
            "product_variant_id", "supplier_product_id", name="uq_supplier_product_mappings_variant_supplier"
        ),
    )

    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("supplier_products.supplier_product_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Denormalized from the mapped supplier_products row at mapping time
    # (ids are only unique within a supplier) so order push can route to
    # the right pharmacy token without a live join.
    supplier_key: Mapped[str] = mapped_column(String(20), nullable=False, server_default="umsrx", default="umsrx")
    # Preserved at mapping time — see class docstring. Not FKs; deliberately
    # decoupled from whatever SupplierProduct.supplier_sku/supplier_name
    # currently say.
    supplier_sku: Mapped[str] = mapped_column(Text, nullable=False)
    supplier_name: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # Sticky, not recomputed: MAPPED / CHANGED / MISSING. Supplier sync
    # reactively downgrades this (see worker/supplier_sync/reconciliation.py)
    # the moment live supplier data drifts from the snapshot above or the
    # supplier product disappears from the feed — but nothing automated
    # ever moves it back to MAPPED. The only way back is
    # app.services.mapping_status.approve_mapping(), a deliberate admin
    # action. See ProductVariant._validate_is_sellable, which gates on
    # this value.
    mapping_status: Mapped[str] = mapped_column(String(20), nullable=False, default="MAPPED", server_default="MAPPED")
    # Why this mapping was made: "EXACT" (catalog_import's own
    # high-confidence match), "LIKELY"/"AMBIGUOUS" (an admin knowingly
    # approved a lower-confidence candidate via /admin/products), or
    # "MANUAL" (an admin picked a supplier product that wasn't even the
    # algorithm's top candidate). Purely informational — never gates
    # anything; mapping_status is what the sellable check reads.
    match_confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="EXACT", server_default="EXACT")

    product_variant: Mapped["ProductVariant"] = relationship(back_populates="supplier_mappings")
    supplier_product: Mapped["SupplierProduct"] = relationship(back_populates="mappings")
