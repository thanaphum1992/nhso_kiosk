from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from app.core.auth import require_admin
from fastapi.templating import Jinja2Templates
from app.api.api import api_router
from app.api.endpoints.kiosk import start_card_reader, stop_card_reader
from app.core import config_manager
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
import os
from dotenv import load_dotenv

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    await start_card_reader(loop)
    yield
    await stop_card_reader()

app = FastAPI(
    title="NHSO Claim API & Kiosk",
    description="System for NHSO Claim Closing and Patient Kiosk",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.include_router(api_router, prefix="/api/v1")

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/kiosk")

@app.get("/admin", response_class=HTMLResponse)
async def index(request: Request, _=Depends(require_admin)):
    env = config_manager.get_env_values()
    force_change = not env.get("ADMIN_PASSWORD", "")
    return templates.TemplateResponse(request, "index.html", {"force_change": force_change})

@app.get("/kiosk", response_class=HTMLResponse)
async def kiosk_page(request: Request):
    load_dotenv(override=True)
    forwarded_for = request.headers.get("x-forwarded-for", "")
    default_client_id = request.query_params.get("client_id") or \
        (forwarded_for.split(",")[0].strip() if forwarded_for else None) or \
        (request.client.host if request.client else "default")
    return templates.TemplateResponse(
        request,
        "kiosk.html",
        {
            "hospital_name": os.getenv("KIOSK_HOSPITAL_NAME", ""),
            "hospital_phone": os.getenv("KIOSK_HOSPITAL_PHONE", ""),
            "auto_reset_sec": int(os.getenv("KIOSK_AUTO_RESET_SEC", "8")),
            "default_client_id": default_client_id,
        },
    )

if __name__ == "__main__":
    import uvicorn
    import sys
    import multiprocessing
    multiprocessing.freeze_support()
    
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
        
    uvicorn.run(app, host="127.0.0.1", port=port)
