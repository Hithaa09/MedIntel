from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_pool, close_pool
from .routers import claims, analytics, patients, ml


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    yield
    close_pool()


app = FastAPI(
    title="MedIntel API",
    description=(
        "REST API powering MedIntel — a healthcare claims analytics platform. "
        "Backed by Oracle XE with Medicare inpatient claims data (CMS dataset). "
        "Includes ML-powered patient risk scoring and provider fraud detection."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(claims.router,    prefix="/api/claims",    tags=["Claims"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(patients.router,  prefix="/api/patients",  tags=["Patients"])
app.include_router(ml.router,        prefix="/api/ml",        tags=["ML"])


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok", "version": app.version}
