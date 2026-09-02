"""HTTP middleware: request logging, CORS, and trusted hosts."""

import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.requests import Request

# Silence uvicorn's default access log; we emit our own line below.
logging.getLogger("uvicorn.access").disabled = True

logger = logging.getLogger("sales_insight")
logging.basicConfig(level=logging.INFO)


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def custom_logging(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        logger.info(
            "%s - %s %s - %s - %.3fs",
            request.client.host if request.client else "?",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],
    )
