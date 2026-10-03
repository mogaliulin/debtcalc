from fastapi import FastAPI

from app.api import auth, debts, me


def create_app() -> FastAPI:
    # CORS не нужен: фронтенд и API отдаются с одного адреса (nginx / прокси Vite),
    # а cookie сессии не должна уходить на чужие сайты.
    app = FastAPI(title="Кредитный калькулятор", version="0.2.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.include_router(auth.router, prefix="/api")
    app.include_router(me.router, prefix="/api")
    app.include_router(debts.router, prefix="/api")

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
