from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import pipeline, config, files

app = FastAPI(title="VFX Agent", version="0.1.0")

def _build_cors_origins() -> list[str]:
    """Build CORS origin list with localhost / 127.0.0.1 alias for dev.

    Prod unaffected (frontend_url is some domain, no alias added).
    Dev: if frontend_url uses localhost, automatically also allow 127.0.0.1
    (and vice versa) — browsers commonly accept either form for the same
    Vite dev server, but CORS treats them as distinct origins.
    """
    origins = [settings.frontend_url]
    try:
        from urllib.parse import urlparse
        u = urlparse(settings.frontend_url)
        if u.hostname == "localhost":
            origins.append(f"{u.scheme}://127.0.0.1:{u.port}")
        elif u.hostname == "127.0.0.1":
            origins.append(f"{u.scheme}://localhost:{u.port}")
    except Exception:
        pass
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)
app.include_router(config.router)
app.include_router(files.router)


@app.on_event("startup")
async def startup_event():
    """Load config from file on startup"""
    config.load_config_from_file()


@app.get("/health")
async def health():
    return {"status": "ok"}