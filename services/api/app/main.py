from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.checkout import orders_router as checkout_orders_router
from app.api.checkout import router as checkout_router
from app.api.health import router as health_router
from app.api.order_requests import admin_router as order_requests_admin_router
from app.api.order_requests import router as order_requests_router
from app.api.shop import router as shop_router
from app.api.webhooks import router as webhooks_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="TimeChain Peptides API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(admin_router)
app.include_router(shop_router)
app.include_router(checkout_router)
app.include_router(checkout_orders_router)
app.include_router(order_requests_router)
app.include_router(order_requests_admin_router)
app.include_router(webhooks_router)
