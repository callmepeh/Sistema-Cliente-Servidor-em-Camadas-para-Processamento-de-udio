"""Entry point do servidor FastAPI.

Execução:
    uvicorn server.app.main:app --reload
ou:
    python -m server.app.main
"""
import uvicorn

from .config import settings
from .database import Base, engine
from .routers import router

try:
    # Ativa os modelos antes de create_all
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
except Exception as exc:  # banco indisponível: servidor sobe, mas /health acusará erro
    print(f"[aviso] Não foi possível sincronizar o schema do banco: {exc}")


def create_app() -> "FastAPI":
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles

    from .config import BASE_DIR

    app = FastAPI(
        title=settings.app_name,
        description=(
            "API do sistema cliente/servidor em camadas para processamento de áudio. "
            "Envie arquivos, aplique processamentos FFmpeg e consulte o histórico."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if origins != ["*"]:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    app.include_router(router, prefix="/api")

    # Redireciona a raiz para a interface web
    from fastapi.responses import RedirectResponse

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/web/index.html")

    # Interface web estática
    web_dir = BASE_DIR / "app" / "web"
    app.mount("/web", StaticFiles(directory=web_dir, html=True), name="web")

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "server.app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
