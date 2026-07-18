from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings  # noqa: F401 — ensure settings loaded early
from app.routes import jobs as jobs_router

app = FastAPI(title="Document Editing Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}
