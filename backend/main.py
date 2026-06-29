from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.excel import router as excel_router
from routers.generate import router as generate_router
from routers.review import router as review_router
from routers.similarity import router as similarity_router
from services import ensure_api_key

app = FastAPI(title="학교생활기록부 작성·검토 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def validate_environment() -> None:
    ensure_api_key()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(generate_router)
app.include_router(review_router)
app.include_router(excel_router)
app.include_router(similarity_router)
