from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes.admin import router as admin_router
from app.routes.ed import router as ed_router
from app.routes.pressao_filtros_ed import router as pressao_filtros_router
from app.routes.tensao_retificadores_ed import router as tensao_retificadores_router
from app.routes.temperatura_forno_ed import router as temperatura_forno_router
from app.routes.web import router as web_router


app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

app.include_router(admin_router)
app.include_router(ed_router)
app.include_router(pressao_filtros_router)
app.include_router(tensao_retificadores_router)
app.include_router(temperatura_forno_router)
app.include_router(web_router)
