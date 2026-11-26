"""
Module: main.py
Mo ta: Diem khoi chay chinh cua FastAPI Backend Server.
       Quan ly Lifespan (khoi tao DB, migration, seed du lieu), CORS va gan cac Routers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import auth, dashboard, hotels, reviews, sync, tasks
from api.services.bootstrap_service import bootstrap_database
from core.logger import get_logger
from database.connection import SessionLocal, init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khoi tao Database, chay migration an toan va nap du lieu nen tang khi bat server."""
    logger.info("Khoi tao co so du lieu va kiem tra migration...")
    init_db()
    db = SessionLocal()
    try:
        bootstrap_database(db)
    finally:
        db.close()
    logger.info("Backend da san sang phuc vu ket noi.")
    yield
    logger.info("Dang dung may chu Backend...")


app = FastAPI(
    title="Hotel ABSA & LLM Management API",
    description=(
        "REST API phuc vu ung dung di dong quan ly va phan tich phan hoi khach hang "
        "linh vuc khach san dua tren PhoBERT ABSA va Google Gemini LLM."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Cau hinh CORS cho phep ket noi tu Android Emulator, thiet bi LAN va Swagger
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dang ky cac nhom Router nghiep vu
app.include_router(auth.router)
app.include_router(hotels.router)
app.include_router(dashboard.router)
app.include_router(reviews.router)
app.include_router(tasks.router)
app.include_router(sync.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Bat cac ngoai le khong mong muon, ghi log va tra ve JSON chuan."""
    logger.exception("Loi he thong tai %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Loi he thong noi bo. Vui long thu lai sau."},
    )


@app.get("/health", tags=["System"])
def health_check():
    """Kiem tra trang thai hoat dong cua may chu API."""
    return {
        "status": "ok",
        "service": "Hotel ABSA & LLM Management API",
        "version": "1.0.0",
    }
