from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, imports, imports_confirm, nlq, overview


def create_app() -> FastAPI:
    app = FastAPI(title="FinanceSync API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(imports.router)
    app.include_router(imports_confirm.router)
    app.include_router(overview.router)
    app.include_router(nlq.router)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

